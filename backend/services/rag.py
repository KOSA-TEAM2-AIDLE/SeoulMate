"""PostgreSQL/pgvector 기반 식당·리뷰·메뉴 가중 RRF 검색."""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from datetime import datetime

import psycopg2
import psycopg2.extras
from openai import OpenAI

from core.config import DB_CONFIG, OPENAI_API_KEY, OPENAI_EMBED_DIM, OPENAI_EMBED_MODEL
from schemas.common import Place
from schemas.structured_query import StructuredQueryTask, StructuredTravelQuery
from services.location import (
    CITYWIDE_LOCATION_NAME,
    address_matches_search_area,
    extract_location,
    geocode_kakao,
    haversine_km,
    is_citywide_location,
    location_candidates,
    wants_citywide_search,
)
from services.query_policy import (
    StructuredRestaurantSearchPlan,
    build_menu_query,
    build_semantic_query,
    derive_source_mode,
    effective_task_filters,
    effective_query_language,
    explicit_feature_fields,
    extract_min_rating,
    prefers_high_rating,
    should_filter_open_now,
    structured_feature_fields,
    target_visit_datetime,
    trusted_budget_bounds,
    trusted_radius_km,
    trusted_time_window,
)


RRF_K = 60
REST_WEIGHT = 0.7
REVIEW_WEIGHT = 2.0
REVIEW_TOP_N = 3
MENU_WEIGHT = 0.5
MENU_TOP_N = 3
NON_MAIN_PENALTY = 0.4
REVIEW_MIN_SIMILARITY = 0.15
MENU_MIN_SIMILARITY = 0.15


def _normalize_unicode_text(value):
    """DB의 분해형 한글을 표시·키워드 매칭에 안정적인 NFC로 통일한다."""
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    return value

# 음식 종류 부스트.
#
# 주의: 부스트는 '일치 후보 사이의 우열'을 가릴 때만 의미가 있다. 확인된 불일치
# (mismatch) 후보는 _select_by_category()에서 제외되므로 점수를 깎아봐야 순위에
# 영향이 없고(그래서 기존 CATEGORY_MISMATCH_PENALTY_PCT는 무의미했다), 일치 후보
# 전원에게 같은 배율을 곱해도 상대 순서는 그대로다.
#
# 따라서 일치를 신뢰도로 등급화해 부스트를 실제 랭킹 신호로 만든다.
#   - CONFIRMED: 카카오 분류(category_kakao)로 확정된 일치
#   - INFERRED : 혼합되기 쉬운 원본 태그(category)로만 추정된 일치
CATEGORY_BOOST_PCT = 0.20
CATEGORY_INFERRED_BOOST_PCT = 0.08

# '평점 좋은 곳'처럼 모호한 선호 표현은 하드 필터가 아니라 가산점이어야 한다.
# 정렬 1순위 키로 쓰면 리뷰 2개짜리 5.0점 신규 가게가 최적합 후보를 이겨버린다.
PREFER_HIGH_RATING_BOOST_PCT = 0.35
RATING_BOOST_BASELINE = 3.5
RATING_BOOST_CEILING = 5.0
RATING_CONFIDENCE_REVIEWS = 30

WARM_MENU_KEYWORDS = {
    "ko": (
        "찌개", "전골", "국물", "국밥", "라멘", "우동", "칼국수", "샤브샤브", "수프",
        "닭한마리", "해장국", "북어국", "미역국", "떡국", "만두국", "육개장", "닭개장",
    ),
    "en": ("soup", "stew", "hot pot", "ramen", "udon", "noodle soup"),
}
COOL_MENU_KEYWORDS = {
    # 샐러드는 따뜻한 고기·피자 곁들임도 많아 '시원한 메뉴' 근거로 쓰지 않는다.
    "ko": ("냉면", "콩국수", "빙수", "아이스크림", "냉모밀", "메밀소바", "냉라면", "냉라멘", "냉우동", "초계탕"),
    "en": ("cold noodles", "naengmyeon", "kongguksu", "bingsu", "ice cream", "cold soba", "cold ramen", "cold udon"),
}

CATEGORY_KEYWORDS = {
    "일본 요리": {
        "user_kw": ["일본 요리", "일본요리", "일식당", "일식", "스시", "초밥", "라멘", "이자카야", "돈까스", "우동"],
        "data_kw": ["일본 요리", "스시", "일본식 퓨전", "이자카야", "일식", "일식집", "일본식주점", "일본식라면", "돈까스", "우동", "초밥", "롤"],
    },
    "한국": {
        "user_kw": ["한식당", "한식", "한정식", "한국음식", "냉면집"],
        "data_kw": ["한국", "한식", "한정식", "냉면", "분식", "삼계탕"],
    },
    "중국 요리": {
        "user_kw": [
            "중국 요리", "중국요리", "중국 음식점", "중국음식점", "중국식당",
            "중식당", "중식", "중국집", "중화요리", "마라샹궈", "마라탕",
            "짜장면", "짬뽕", "탕수육",
        ],
        "data_kw": ["중국 요리", "중식", "중국요리"],
    },
    "이탈리아 요리": {
        "user_kw": ["이탈리아 요리", "이탈리아요리", "이탈리안", "이태리", "파스타집"],
        # '양식'은 프렌치·스테이크 등도 포함하는 광범위한 태그라 이탈리안 확정 근거로 쓰지 않는다.
        "data_kw": ["이탈리아 요리", "이탈리안"],
    },
    "바베큐": {
        "user_kw": ["고깃집", "바베큐", "삼겹살", "갈비집", "곱창집", "막창집", "족발집", "보쌈집"],
        "data_kw": ["바베큐", "고기", "육류", "갈비", "곱창", "막창", "족발", "보쌈", "그릴", "삼겹살", "립", "불고기"],
    },
    "와인 바": {"user_kw": ["와인 바", "와인바"], "data_kw": ["와인 바", "와인바"]},
    "바": {
        "user_kw": ["바", "펍", "술집", "호프집", "요리주점", "칵테일바"],
        "data_kw": ["바", "펍", "호프", "요리주점", "칵테일바", "다이닝 바", "맥주 음식점", "자가 맥주 판매pub", "개스트로펍", "술집"],
    },
    "스테이크하우스": {"user_kw": ["스테이크하우스", "스테이크집"], "data_kw": ["스테이크하우스", "스테이크"]},
    "해산물": {
        "user_kw": ["해산물", "씨푸드", "횟집", "회집", "회센터", "물회"],
        "data_kw": ["해산물", "해물", "생선", "조개", "게", "대게", "바닷가재", "해산물뷔페"],
    },
    "인도 요리": {"user_kw": ["인도 요리", "인도음식", "커리집"], "data_kw": ["인도 요리", "인도음식"]},
    "멕시코 요리": {"user_kw": ["멕시칸", "멕시코 요리", "타코집", "부리또"], "data_kw": ["멕시코 요리", "멕시칸"]},
    "프랑스 요리": {"user_kw": ["프렌치", "프랑스 요리", "프렌치 레스토랑"], "data_kw": ["프랑스 요리"]},
    "타이 요리": {"user_kw": ["타이 요리", "타이 음식점", "타이음식점", "태국 요리", "태국 음식점", "태국음식점", "태국 음식", "태국음식", "팟타이집"], "data_kw": ["타이 요리", "태국음식"]},
    "스페인 요리": {"user_kw": ["스페인 요리", "타파스"], "data_kw": ["스페인 요리"]},
    "피자": {"user_kw": ["피자집", "피자"], "data_kw": ["피자"]},
    "카페": {"user_kw": ["카페", "커피숍", "디저트카페", "브런치카페"], "data_kw": ["카페", "디저트카페", "테마카페", "제과", "베이커리"]},
    "베트남 요리": {"user_kw": ["베트남 요리", "베트남음식", "쌀국수집", "반미"], "data_kw": ["베트남 요리", "베트남음식"]},
}

CATEGORY_USER_KEYWORDS_EN = {
    "일본 요리": ["japanese restaurant", "japanese food", "sushi", "ramen", "izakaya", "udon"],
    "한국": ["korean restaurant", "korean food", "hansik", "naengmyeon"],
    "중국 요리": ["chinese restaurant", "chinese food", "chinese cuisine"],
    "이탈리아 요리": ["italian restaurant", "italian food", "pasta"],
    "바베큐": ["barbecue", "bbq", "korean bbq"],
    "해산물": ["seafood restaurant", "seafood"],
    "인도 요리": ["indian restaurant", "indian food", "curry"],
    "멕시코 요리": ["mexican restaurant", "mexican food", "tacos"],
    "카페": ["cafe", "coffee shop", "bakery cafe"],
}
CATEGORY_DATA_KEYWORDS_EN = {
    "일본 요리": ["japanese", "sushi", "ramen", "izakaya"],
    "한국": ["korean", "korean food"],
    "중국 요리": ["chinese", "chinese food"],
    "이탈리아 요리": ["italian", "pizza", "pasta"],
    "바베큐": ["barbecue", "bbq", "grill"],
    "해산물": ["seafood"],
    "인도 요리": ["indian"],
    "멕시코 요리": ["mexican"],
    "카페": ["cafe", "coffee", "bakery"],
    "와인 바": ["wine bar"],
    "바": ["bar", "pub", "gastropub"],
    "스테이크하우스": ["steakhouse", "steak house"],
    "프랑스 요리": ["french"],
    "타이 요리": ["thai"],
    "스페인 요리": ["spanish", "tapas"],
    "피자": ["pizza"],
    "베트남 요리": ["vietnamese"],
}

# 이 표현들은 단순 음식군이 아니라 사용자가 실제로 먹고 싶다고 지정한 메뉴다.
# 벡터 유사도만 사용하면 "마라탕"이 "마라 비프" 식당으로 바뀔 수 있으므로,
# 구조화 검색에서는 메뉴 테이블에 아래 표현이 확인된 식당만 통과시킨다.
SPECIFIC_MENU_ALIASES = {
    "ko": {
        "떡볶이": ("떡볶이",),
        "쌀국수": ("쌀국수",),
        "마라탕": ("마라탕",),
        "마라샹궈": ("마라샹궈",),
        "짜장면": ("짜장면", "자장면"),
        "짬뽕": ("짬뽕",),
        "탕수육": ("탕수육",),
        "초밥": ("초밥", "스시"),
        "라멘": ("라멘", "라면"),
        "돈까스": ("돈까스", "돈가스"),
        "우동": ("우동",),
        "냉면": ("냉면",),
        "물회": ("물회",),
        "팟타이": ("팟타이",),
        "타코": ("타코",),
        "부리또": ("부리또", "부리토"),
        "반미": ("반미",),
    },
    "en": {
        "tteokbokki": ("tteokbokki",),
        "pho": ("pho",),
        "malatang": ("malatang", "mala tang"),
        "sushi": ("sushi",),
        "ramen": ("ramen",),
        "udon": ("udon",),
        "pad thai": ("pad thai",),
        "taco": ("taco", "tacos"),
        "burrito": ("burrito", "burritos"),
        "banh mi": ("banh mi",),
    },
}

SUFFIX_OK = "집당점곳"
MIN_FUZZY_LEN = 4
DAY_MAP = {
    "월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}
HOURS_RE = re.compile(
    r"(월|화|수|목|금|토|일|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*"
    r"(\d{1,2}):(\d{2})~(\d{1,2}):(\d{2})",
    re.IGNORECASE,
)


def _client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")
    return OpenAI(api_key=OPENAI_API_KEY)


def _connection():
    return psycopg2.connect(**DB_CONFIG)


def _extract_required_menu_terms(text: str, lang: str) -> tuple[str, ...]:
    lowered = str(text or "").casefold()
    aliases = SPECIFIC_MENU_ALIASES["en" if lang == "en" else "ko"]
    matched: list[str] = []
    for user_term, menu_terms in aliases.items():
        if lang == "en":
            present = bool(re.search(rf"\b{re.escape(user_term)}\b", lowered))
        else:
            present = user_term in lowered
        if present:
            matched.extend(menu_terms)
    return tuple(dict.fromkeys(matched))


def _ids_with_required_menus(
    cursor,
    table_suffix: str,
    menu_terms: tuple[str, ...],
    restaurant_ids: list[int] | None,
) -> list[int]:
    if not menu_terms:
        return restaurant_ids or []
    menu_clauses = " OR ".join("menu_name ILIKE %s" for _ in menu_terms)
    params: list[object] = [f"%{term}%" for term in menu_terms]
    restaurant_filter = ""
    if restaurant_ids is not None:
        restaurant_filter = " AND restaurant_id = ANY(%s)"
        params.append(restaurant_ids)
    cursor.execute(
        f"""
            SELECT DISTINCT restaurant_id
            FROM restaurant_menu_{table_suffix}
            WHERE ({menu_clauses}){restaurant_filter}
        """,
        params,
    )
    return [row["restaurant_id"] for row in cursor.fetchall()]


def _exact_match(query: str, keyword: str) -> str | None:
    if len(keyword) <= 2:
        pattern = rf"(?<![가-힣]){re.escape(keyword)}[{SUFFIX_OK}]?(?=[^가-힣]|$)"
    else:
        pattern = re.escape(keyword)
    if not re.search(pattern, query):
        return None
    return re.sub(r"\s+", " ", re.sub(pattern, "", query)).strip()


def _fuzzy_match(query: str, keyword: str) -> tuple[str, float] | None:
    if len(keyword) < MIN_FUZZY_LEN or len(query) < len(keyword):
        return None
    threshold = 0.75 if len(keyword) == 4 else 0.80
    best: tuple[float, int, int] | None = None
    for index in range(len(query) - len(keyword) + 1):
        window = query[index:index + len(keyword)]
        if window[0] != keyword[0]:
            continue
        ratio = difflib.SequenceMatcher(None, window, keyword).ratio()
        if best is None or ratio > best[0]:
            best = (ratio, index, index + len(keyword))
    if not best or best[0] < threshold:
        return None
    ratio, start, end = best
    cleaned = re.sub(r"\s+", " ", query[:start] + query[end:]).strip()
    return cleaned, ratio


def extract_category(query: str, lang: str = "ko") -> tuple[str | None, str]:
    if lang == "en":
        lowered = query.lower()
        matches = [
            (category, keyword)
            for category, keywords in CATEGORY_USER_KEYWORDS_EN.items()
            for keyword in keywords
            if re.search(rf"\b{re.escape(keyword)}\b", lowered)
        ]
        if not matches:
            return None, query
        category, keyword = max(matches, key=lambda item: len(item[1]))
        cleaned = re.sub(rf"\b{re.escape(keyword)}\b", " ", query, flags=re.IGNORECASE)
        return category, re.sub(r"\s+", " ", cleaned).strip()

    keywords = [
        (category, keyword)
        for category, spec in CATEGORY_KEYWORDS.items()
        for keyword in spec["user_kw"]
    ]
    keywords.sort(key=lambda item: -len(item[1]))
    for category, keyword in keywords:
        cleaned = _exact_match(query, keyword)
        if cleaned is not None:
            return category, cleaned
    matches = []
    for category, keyword in keywords:
        result = _fuzzy_match(query, keyword)
        if result:
            cleaned, ratio = result
            matches.append((ratio, category, cleaned))
    if matches:
        _, category, cleaned = max(matches)
        return category, cleaned
    return None, query


def _category_match_status(meta: dict, requested_category: str | None) -> tuple[str, str | None]:
    """(status, confidence)를 반환한다.

    status     : "match" | "mismatch" | "no_data" | "n/a"  (기존 계약 그대로 유지)
    confidence : "confirmed"(카카오 분류로 확정) | "inferred"(원본 태그로 추정) | None

    기존 구현은 두 종류의 일치를 똑같은 "match"로 뭉갰다. 그래서 일치 후보 전원이
    같은 부스트를 받아 부스트가 순위를 전혀 바꾸지 못했다. 신뢰도를 분리해야
    부스트가 실제 랭킹 신호로 작동한다.
    """
    if not requested_category:
        return "n/a", None

    def tags(value: str | None) -> set[str]:
        return {tag.strip().lower() for tag in str(value or "").split(",") if tag.strip()}

    def canonical_categories(category_tags: set[str]) -> set[str]:
        return {
            category
            for category, spec in CATEGORY_KEYWORDS.items()
            if any(
                keyword in category_tags
                for keyword in [
                    *[keyword.lower() for keyword in spec["data_kw"]],
                    *CATEGORY_DATA_KEYWORDS_EN.get(category, []),
                ]
            )
        }

    kakao_tags = tags(meta.get("category_kakao"))
    kakao_categories = canonical_categories(kakao_tags)
    if requested_category in kakao_categories:
        return "match", "confirmed"
    # 카카오 분류가 다른 음식군으로 명확하면 혼합 원본 태그보다 우선한다.
    if kakao_categories:
        return "mismatch", "confirmed"

    all_tags = tags(meta.get("category")) | kakao_tags
    if requested_category in canonical_categories(all_tags):
        return "match", "inferred"
    # 알려진 다른 음식군으로 해석될 때만 mismatch다. 단순히 낯선/광범위 태그가
    # 있다는 이유로 명시적 음식 종류와 불일치한다고 단정하지 않는다.
    if canonical_categories(all_tags):
        return "mismatch", "inferred"
    return "no_data", None


def _category_adjustment_status(meta: dict, requested_category: str | None) -> str:
    """기존 호출부 호환용: 신뢰도는 버리고 match 상태만 반환한다."""
    return _category_match_status(meta, requested_category)[0]


def _category_boost(base_score: float, status: str, confidence: str | None) -> float:
    """음식 종류 일치 부스트. 확정 일치를 추정 일치보다 확실히 위로 올린다."""
    if status != "match":
        return 0.0
    pct = CATEGORY_BOOST_PCT if confidence == "confirmed" else CATEGORY_INFERRED_BOOST_PCT
    return base_score * pct


def _rating_preference_boost(
    base_score: float,
    rating: float | None,
    review_count: int | None,
    prefer_high_rating: bool,
) -> float:
    """평점 선호를 정렬 지배가 아닌 유계 가산점으로 반영한다.

    리뷰 수가 적을수록 평점 신뢰도가 낮으므로 가산점도 함께 줄인다.
    """
    if not prefer_high_rating or rating is None:
        return 0.0
    span = RATING_BOOST_CEILING - RATING_BOOST_BASELINE
    normalized = min(max(rating - RATING_BOOST_BASELINE, 0.0), span) / span
    confidence = min(review_count or 0, RATING_CONFIDENCE_REVIEWS) / RATING_CONFIDENCE_REVIEWS
    return base_score * PREFER_HIGH_RATING_BOOST_PCT * normalized * confidence


def _select_by_category(candidates: list[dict], requested_category: str | None) -> tuple[list[dict], bool]:
    """명시적 음식 종류는 soft preference가 아니라 검색 조건이다.

    확인된 일치 후보를 우선하고, 메타데이터가 없는 후보만 recall용 fallback으로 남긴다.
    다른 음식군으로 확인된 후보(mismatch)는 순위를 낮추는 게 아니라 제외한다.
    일치/미상 후보가 하나도 없으면 '해당 종류를 찾지 못했다'는 사실을 호출자에게 알린다.
    """
    if not requested_category:
        return candidates, False
    matched = [item for item in candidates if item["breakdown"]["category_status"] == "match"]
    if matched:
        return matched, False
    unknown = [item for item in candidates if item["breakdown"]["category_status"] == "no_data"]
    return unknown, not unknown


def is_open_at(hours_text: str | None, target: datetime) -> bool | None:
    if not hours_text:
        return None
    today, yesterday = target.weekday(), (target.weekday() - 1) % 7
    current = target.hour * 60 + target.minute
    parsed = False
    for match in HOURS_RE.finditer(hours_text):
        day, sh, sm, eh, em = match.groups()
        parsed = True
        start, end = int(sh) * 60 + int(sm), int(eh) * 60 + int(em)
        weekday = DAY_MAP[day.lower()]
        if end > start and weekday == today and start <= current < end:
            return True
        if end <= start and ((weekday == today and current >= start) or (weekday == yesterday and current < end)):
            return True
    return False if parsed else None


def is_open_now(hours_text: str | None, now: datetime | None = None) -> bool | None:
    return is_open_at(hours_text, now or datetime.now())


def _review_length_coef(text: str) -> float:
    word_count = len(str(text).split())
    return 0.3 if word_count < 4 else 0.8 if word_count < 7 else 1.0


def _embedding(text: str) -> list[float]:
    response = _client().embeddings.create(
        model=OPENAI_EMBED_MODEL,
        input=[text],
        dimensions=OPENAI_EMBED_DIM,
    )
    return response.data[0].embedding


def _vector_literal(vector: list[float]) -> str:
    return json.dumps(vector, separators=(",", ":"))


def _ids_within_radius(cursor, lat: float, lng: float, radius_km: float, table: str) -> list[int]:
    cursor.execute(f"SELECT id, lat, lng FROM {table} WHERE lat IS NOT NULL AND lng IS NOT NULL")
    return [
        row["id"] for row in cursor.fetchall()
        if haversine_km(lat, lng, row["lat"], row["lng"]) <= radius_km
    ]


def _vector_search(
    cursor,
    table_suffix: str,
    vector: list[float],
    review_vector: list[float],
    menu_vector: list[float],
    restaurant_ids: list[int] | None,
):
    literal = _vector_literal(vector)
    review_literal = _vector_literal(review_vector)
    menu_literal = _vector_literal(menu_vector)
    filter_rest = "WHERE restaurant_id = ANY(%s)" if restaurant_ids is not None else ""
    filter_review = "WHERE rv.restaurant_id = ANY(%s)" if restaurant_ids is not None else ""
    filter_menu = "WHERE mn.restaurant_id = ANY(%s)" if restaurant_ids is not None else ""

    def params(limit: int) -> list:
        return [literal, *([restaurant_ids] if restaurant_ids is not None else []), literal, limit]

    review_params = [review_literal, *([restaurant_ids] if restaurant_ids is not None else []), review_literal, 250]
    menu_params = [menu_literal, *([restaurant_ids] if restaurant_ids is not None else []), menu_literal, 250]
    cursor.execute(f"""
        SELECT restaurant_id, embedding <=> %s::vector AS distance
        FROM restaurant_embedding_{table_suffix}
        {filter_rest}
        ORDER BY embedding <=> %s::vector, restaurant_id
        LIMIT %s
    """, params(100))
    restaurant_hits = {
        row["restaurant_id"]: {"rank": rank, "similarity": 1 - float(row["distance"])}
        for rank, row in enumerate(cursor.fetchall(), 1)
    }

    cursor.execute(f"""
        SELECT rv.restaurant_id, rv.id AS review_id, re.content,
               re.embedding <=> %s::vector AS distance
        FROM review_embedding_{table_suffix} re
        JOIN restaurant_review_{table_suffix} rv ON rv.id = re.review_id
        {filter_review}
        ORDER BY re.embedding <=> %s::vector, rv.id
        LIMIT %s
    """, review_params)
    review_hits: dict[int, list[dict]] = {}
    for rank, row in enumerate(cursor.fetchall(), 1):
        review_hits.setdefault(row["restaurant_id"], []).append({
            "rank": rank,
            "review_id": row["review_id"],
            "content": _normalize_unicode_text(row["content"]),
            "similarity": 1 - float(row["distance"]),
        })

    cursor.execute(f"""
        SELECT mn.restaurant_id, mn.id AS menu_id, mn.menu_name, mn.is_main,
               me.embedding <=> %s::vector AS distance
        FROM menu_embedding_{table_suffix} me
        JOIN restaurant_menu_{table_suffix} mn ON mn.id = me.menu_id
        {filter_menu}
        ORDER BY me.embedding <=> %s::vector, mn.id
        LIMIT %s
    """, menu_params)
    menu_hits: dict[int, list[dict]] = {}
    for rank, row in enumerate(cursor.fetchall(), 1):
        menu_hits.setdefault(row["restaurant_id"], []).append({
            "rank": rank,
            "menu_id": row["menu_id"],
            "menu_name": _normalize_unicode_text(row["menu_name"]),
            "is_main": bool(row["is_main"]),
            "similarity": 1 - float(row["distance"]),
        })
    return restaurant_hits, review_hits, menu_hits


def _contains_menu_keyword(menu_name: str, keywords: tuple[str, ...], lang: str) -> bool:
    text = str(menu_name or "").strip().lower()
    if lang == "en":
        return any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in keywords)
    return any(keyword in text for keyword in keywords)


def _is_warm_menu(menu_name: str, lang: str) -> bool:
    text = str(menu_name or "").strip()
    if lang == "ko":
        # 이름에 우동·라멘이 있어도 냉·비빔·볶음 조리면 따뜻한 국물 근거가 아니다.
        non_soup_noodles = ("냉우동", "비빔우동", "볶음우동", "야끼우동", "냉라멘", "냉라면")
        if "초계탕" in text or any(word in text for word in non_soup_noodles):
            other_keywords = tuple(
                keyword for keyword in WARM_MENU_KEYWORDS[lang]
                if keyword not in {"우동", "라멘"}
            )
            return _contains_menu_keyword(text, other_keywords, lang)
    else:
        non_soup_noodles = ("cold udon", "yaki udon", "stir-fried udon", "cold ramen")
        if any(word in text.lower() for word in non_soup_noodles):
            other_keywords = tuple(
                keyword for keyword in WARM_MENU_KEYWORDS[lang]
                if keyword not in {"udon", "ramen"}
            )
            return _contains_menu_keyword(text, other_keywords, lang)
    if _contains_menu_keyword(text, WARM_MENU_KEYWORDS[lang], lang):
        return True
    # '탕수육', '탕후루', '무설탕'처럼 따뜻한 국물 메뉴가 아닌 오탐을 제외한다.
    return (
        lang == "ko"
        and not any(word in text for word in ("설탕", "사탕"))
        and re.search(r"탕(?![가-힣])", text) is not None
    )


def _is_cool_menu(menu_name: str, lang: str) -> bool:
    text = str(menu_name or "").strip()
    return _contains_menu_keyword(text, COOL_MENU_KEYWORDS[lang], lang)


def _build_weather_menu_features(
    rows: list[dict], restaurant_ids: list[int], lang: str
) -> dict[int, dict]:
    """전체 메뉴로 날씨 태그를 만들고 표시 근거는 대표·메뉴 순서대로 3개만 남긴다."""
    suffix = "en" if lang == "en" else "ko"
    features = {
        restaurant_id: {
            "has_warm_menu": False,
            "has_cool_menu": False,
            "warm_menu_matches": [],
            "cool_menu_matches": [],
        }
        for restaurant_id in restaurant_ids
    }
    for row in rows:
        feature = features[row["restaurant_id"]]
        menu_name = str(row.get("menu_name") or "").strip()
        if not menu_name:
            continue
        if _is_warm_menu(menu_name, suffix):
            feature["has_warm_menu"] = True
            if menu_name not in feature["warm_menu_matches"] and len(feature["warm_menu_matches"]) < 3:
                feature["warm_menu_matches"].append(menu_name)
        if _is_cool_menu(menu_name, suffix):
            feature["has_cool_menu"] = True
            if menu_name not in feature["cool_menu_matches"] and len(feature["cool_menu_matches"]) < 3:
                feature["cool_menu_matches"].append(menu_name)
    return features


def _load_weather_menu_features(
    table_suffix: str, restaurant_ids: list[int]
) -> dict[int, dict]:
    if not restaurant_ids:
        return {}
    with _connection() as connection:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(f"""
                SELECT restaurant_id, menu_name, is_main, menu_order
                FROM restaurant_menu_{table_suffix}
                WHERE restaurant_id = ANY(%s)
                ORDER BY restaurant_id, is_main DESC, menu_order ASC, id ASC
            """, (restaurant_ids,))
            rows = cursor.fetchall()
    return _build_weather_menu_features(rows, restaurant_ids, table_suffix)


# 지오코딩은 "강남"도 강남역 지점으로 수렴시키므로, 사용자가 지역(구/동네)을
# 말했는지 특정 지점(역/랜드마크)을 말했는지에 따라 기본 반경을 달리한다.
STATION_DEFAULT_RADIUS_KM = 2.0   # "강남역" 같은 특정 지점 → 역 근처만
DISTRICT_DEFAULT_RADIUS_KM = 5.0  # "강남구" 같은 자치구 → 넓게
AREA_DEFAULT_RADIUS_KM = 4.0      # "강남/홍대" 같은 동네 → 지역 전체를 아우름
CITYWIDE_RADIUS_KM = 60.0         # "서울" → 도시 전역(사실상 반경 무제한)
CITYWIDE_TERMS = {"서울", "서울시", "서울특별시", "seoul"}


def _area_default_radius(location: str | None) -> float:
    """지오코딩 전 사용자 원본 지명으로 기본 검색 반경을 정한다."""
    if not location:
        return STATION_DEFAULT_RADIUS_KM
    text = location.strip().lower()
    # 도시 전역
    if text in CITYWIDE_TERMS:
        return CITYWIDE_RADIUS_KM
    # 지하철역/특정 지점: 역 근처만 좁게
    if text.endswith("역") or text.endswith("station") or "번 출구" in text:
        return STATION_DEFAULT_RADIUS_KM
    # 자치구 단위: 가장 넓게
    if text.endswith("구") or text.endswith("-gu"):
        return DISTRICT_DEFAULT_RADIUS_KM
    # 그 외 동네/지역명(강남, 홍대, 이태원 등)은 지역 전체를 아우른다.
    return AREA_DEFAULT_RADIUS_KM


def build_restaurant_search_plan(
    parsed_query: StructuredTravelQuery,
    task: StructuredQueryTask,
    *,
    current_lat: float | None = None,
    current_lng: float | None = None,
    current_location_name: str | None = None,
    top_n: int = 30,
) -> StructuredRestaurantSearchPlan:
    """GPT가 만든 Task/Filter를 기존 식당 RRF 검색에 필요한 값으로 변환한다."""
    if task.domain != "restaurant":
        raise ValueError(f"RestaurantAgent에 {task.domain} Task를 전달할 수 없습니다.")

    task_filters = effective_task_filters(parsed_query, task)
    task_query = parsed_query.model_copy(update={"filters": task_filters})
    semantic_query = build_semantic_query(task, task_filters)
    language = effective_query_language(parsed_query)
    category, category_cleaned = extract_category(semantic_query, language)
    if category is None:
        # GPT가 영문 질문을 한국어 search_query로 번역해도 원문 음식군은 잃지 않는다.
        category, _ = extract_category(parsed_query.original_question, language)

    # 리뷰는 음식 종류보다 분위기·목적 theme가 중요하므로 카테고리 표현을 제거한 문장을 쓴다.
    review_parts = [category_cleaned]
    review_lowered = category_cleaned.lower()
    semantic_lowered = semantic_query.lower()
    for theme in task.themes:
        # 평점·가격처럼 semantic query에서 제거된 hard-filter theme는 리뷰 벡터에도 넣지 않는다.
        if (
            theme.strip()
            and theme.lower() in semantic_lowered
            and theme.lower() not in review_lowered
        ):
            review_parts.append(theme.strip())
    review_query = " ".join(part for part in review_parts if part).strip() or semantic_query

    source_mode = derive_source_mode(parsed_query)
    location_name = task_filters.location
    # 반경 판정은 정규화 전 사용자 원본 지명으로 한다. effective_task_filters는
    # "강남역"을 "강남"으로 정규화해 역 근처 의도를 잃을 수 있으므로, Task/전역
    # 필터의 원본 location을 우선 사용한다. (지오코딩 좌표는 어차피 동일)
    requested_location_term = (
        (task.filters.location if task.filters else None)
        or parsed_query.filters.location
        or location_name
    )
    origin_lat, origin_lng = current_lat, current_lng
    citywide_search = is_citywide_location(location_name)
    same_as_current = bool(
        location_name
        and current_location_name
        and current_lat is not None
        and current_lng is not None
        and location_name.strip().lower() == current_location_name.strip().lower()
    )
    # 타깃 위치가 있는데 현재 좌표의 지명과 같다는 근거가 없으면 반드시 타깃을
    # 지오코딩한다. location_name=None인 사용자 좌표를 홍대/강남 좌표로 오인하지 않는다.
    if citywide_search:
        location_name = CITYWIDE_LOCATION_NAME
        origin_lat, origin_lng = None, None
    elif location_name and not same_as_current:
        geocoded = geocode_kakao(location_name)
        if geocoded:
            origin_lat, origin_lng, location_name = geocoded
        else:
            # 서로 다른 현재 위치 좌표로 잘못 필터링하는 것보다 거리 필터를 끄는 편이 안전하다.
            origin_lat, origin_lng = None, None
    budget_min_krw, budget_max_krw = trusted_budget_bounds(task_query)
    return StructuredRestaurantSearchPlan(
        task_id=task.task_id,
        retrieval_query=semantic_query,
        review_query=review_query,
        menu_query=build_menu_query(task, task_filters),
        required_menu_terms=_extract_required_menu_terms(
            build_menu_query(task, task_filters), language
        ),
        requested_category=category,
        location_name=location_name,
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        radius_km=None if citywide_search else trusted_radius_km(
            task_query, default=_area_default_radius(requested_location_term)
        ),
        citywide_search=citywide_search,
        open_now=should_filter_open_now(task_query, task_filters),
        include_weather_features=source_mode == "rag_mcp",
        min_rating=extract_min_rating(task_query),
        prefer_high_rating=prefers_high_rating(task_query),
        required_feature_fields=tuple(dict.fromkeys([
            *structured_feature_fields([
                *task_filters.required_features,
                *task_filters.accessibility,
                *task_filters.transportation,
            ]),
            *explicit_feature_fields(task_query),
        ])),
        excluded_feature_fields=structured_feature_fields(task_filters.excluded_features),
        target_time_window=trusted_time_window(task_query),
        target_visit_at=target_visit_datetime(task_query),
        budget_min_krw=budget_min_krw,
        budget_max_krw=budget_max_krw,
        top_n=max(top_n, task.desired_count),
        search_area_name=requested_location_term,
    )


def search_restaurants_structured(
    parsed_query: StructuredTravelQuery,
    task: StructuredQueryTask,
    *,
    current_lat: float | None = None,
    current_lng: float | None = None,
    current_location_name: str | None = None,
    min_rating: float | None = None,
    top_n: int = 30,
) -> dict:
    """구조화된 Restaurant Task를 검색한다. 원문 위치·날짜 키워드를 다시 파싱하지 않는다."""
    plan = build_restaurant_search_plan(
        parsed_query,
        task,
        current_lat=current_lat,
        current_lng=current_lng,
        current_location_name=current_location_name,
        top_n=top_n,
    )
    # 명시된 지역을 좌표로 바꾸지 못했다면 서울 전체 검색으로 폴백하지 않는다.
    # 빈 결과와 원인을 반환해 상위 계층이 지역 재입력을 요청할 수 있게 한다.
    if (
        plan.location_name
        and not plan.citywide_search
        and (plan.origin_lat is None or plan.origin_lng is None)
    ):
        return {
            "candidates": [],
            "location_name": plan.location_name,
            "origin_lat": None,
            "origin_lng": None,
            "extracted_category": plan.requested_category,
            "cleaned_query": plan.retrieval_query,
            "category_no_match": False,
            "menu_no_match": False,
            "required_menu_terms": list(plan.required_menu_terms),
            "location_resolution_failed": True,
            "task_id": task.task_id,
            "source_mode": derive_source_mode(parsed_query),
            "structured_input": True,
        }
    result = search_restaurants(
        plan.retrieval_query,
        lang=effective_query_language(parsed_query),
        min_rating=min_rating if min_rating is not None else plan.min_rating,
        open_now=plan.open_now,
        radius_km=plan.radius_km,
        top_n=plan.top_n,
        _structured_plan=plan,
    )
    result["task_id"] = task.task_id
    result["source_mode"] = derive_source_mode(parsed_query)
    result["structured_input"] = True
    result["citywide_search"] = plan.citywide_search
    result.setdefault("location_resolution_failed", False)
    return result


def search_restaurants(
    query: str,
    lang: str = "ko",
    min_rating: float | None = None,
    open_now: bool = False,
    radius_km: float | None = 2.0,
    top_n: int = 30,
    *,
    _structured_plan: StructuredRestaurantSearchPlan | None = None,
) -> dict:
    suffix = "en" if str(lang).lower().startswith("en") else "ko"
    if _structured_plan:
        category = _structured_plan.requested_category
        location_name = _structured_plan.location_name
        origin_lat = _structured_plan.origin_lat
        origin_lng = _structured_plan.origin_lng
        semantic_query = _structured_plan.retrieval_query
        review_query = _structured_plan.review_query
        menu_query = _structured_plan.menu_query
        original_vector = _embedding(semantic_query)
        review_vector = (
            _embedding(review_query) if review_query != semantic_query else original_vector
        )
        if menu_query == semantic_query:
            menu_vector = original_vector
        elif menu_query == review_query:
            menu_vector = review_vector
        else:
            menu_vector = _embedding(menu_query)
    else:
        category, cleaned_query = extract_category(query) if suffix == "ko" else (None, query)
        legacy_citywide = wants_citywide_search(cleaned_query)
        requested_location_candidates = location_candidates(cleaned_query)
        if legacy_citywide:
            location_name = CITYWIDE_LOCATION_NAME
            origin_lat, origin_lng = None, None
        else:
            location_name, origin_lat, origin_lng, cleaned_query = extract_location(cleaned_query)
        semantic_query = cleaned_query or query
        # 레거시 원문 검색도 '지역처럼 보이는 표현은 있었지만 지오코딩 실패' 시
        # 서울 전체 결과를 반환하지 않는다.
        if requested_location_candidates and origin_lat is None and not legacy_citywide:
            return {
                "candidates": [],
                "location_name": requested_location_candidates[0],
                "origin_lat": None,
                "origin_lng": None,
                "extracted_category": category,
                "cleaned_query": semantic_query,
                "category_no_match": False,
                "menu_no_match": False,
                "required_menu_terms": [],
                "location_resolution_failed": True,
            }
        original_vector = _embedding(query)
        review_vector = _embedding(semantic_query) if semantic_query != query else original_vector
        menu_vector = original_vector

    with _connection() as connection:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            restaurant_ids = None
            if (
                origin_lat is not None
                and origin_lng is not None
                and radius_km is not None
            ):
                restaurant_ids = _ids_within_radius(
                    cursor, origin_lat, origin_lng, radius_km, f"restaurant_{suffix}"
                )
                if not restaurant_ids:
                    return {
                        "candidates": [], "location_name": location_name,
                        "origin_lat": origin_lat, "origin_lng": origin_lng,
                        "extracted_category": category, "cleaned_query": semantic_query,
                        "category_no_match": False,
                    }

            required_menu_terms = (
                _structured_plan.required_menu_terms if _structured_plan else ()
            )
            if required_menu_terms:
                restaurant_ids = _ids_with_required_menus(
                    cursor, suffix, required_menu_terms, restaurant_ids
                )
                if not restaurant_ids:
                    return {
                        "candidates": [], "location_name": location_name,
                        "origin_lat": origin_lat, "origin_lng": origin_lng,
                        "extracted_category": category, "cleaned_query": semantic_query,
                        "category_no_match": False, "menu_no_match": True,
                        "required_menu_terms": list(required_menu_terms),
                    }

            rest_hits, review_hits, menu_hits = _vector_search(
                cursor, suffix, original_vector, review_vector, menu_vector, restaurant_ids
            )
            all_ids = set(rest_hits) | set(review_hits) | set(menu_hits)
            if not all_ids:
                return {
                    "candidates": [], "location_name": location_name,
                    "origin_lat": origin_lat, "origin_lng": origin_lng,
                    "extracted_category": category, "cleaned_query": semantic_query,
                    "category_no_match": False,
                }

            cursor.execute(f"""
                SELECT id, name, category, category_kakao, rating, review_count, hours,
                       description, description_kakao, address, image, link, lat, lng,
                       menu_price_min, menu_price_median,
                       mp.menu_price_lo, mp.menu_price_hi,
                       has_parking, allows_pets, has_kids_menu,
                       has_group_seating, has_private_room, has_baby_chair,
                       has_disabled_access
                FROM restaurant_{suffix}
                LEFT JOIN LATERAL (
                    SELECT MIN(price_value) AS menu_price_lo,
                           MAX(price_value) AS menu_price_hi
                    FROM restaurant_menu_{suffix} rm
                    WHERE rm.restaurant_id = restaurant_{suffix}.id
                ) mp ON TRUE
                WHERE id = ANY(%s)
            """, (list(all_ids),))
            metadata = {row["id"]: row for row in cursor.fetchall()}

    candidates = []
    for restaurant_id in all_ids:
        meta = metadata.get(restaurant_id)
        if not meta:
            continue
        passes_filters, open_status, open_status_basis = _passes_candidate_filters(
            meta,
            _structured_plan,
            min_rating=min_rating,
            open_now=open_now,
        )
        if not passes_filters:
            continue

        rest_score = REST_WEIGHT / (RRF_K + rest_hits[restaurant_id]["rank"]) if restaurant_id in rest_hits else 0.0
        reviews = [hit for hit in review_hits.get(restaurant_id, []) if hit["similarity"] >= REVIEW_MIN_SIMILARITY]
        reviews = sorted(reviews, key=lambda hit: hit["rank"])[:REVIEW_TOP_N]
        review_score = REVIEW_WEIGHT * sum(
            _review_length_coef(hit["content"]) / (RRF_K + hit["rank"]) for hit in reviews
        )
        menus = [hit for hit in menu_hits.get(restaurant_id, []) if hit["similarity"] >= MENU_MIN_SIMILARITY]
        menus = sorted(menus, key=lambda hit: hit["rank"])[:MENU_TOP_N]
        menu_score = MENU_WEIGHT * sum(
            (1.0 if hit["is_main"] else NON_MAIN_PENALTY) / (RRF_K + hit["rank"])
            for hit in menus
        )
        base_score = rest_score + review_score + menu_score

        category_status, category_confidence = _category_match_status(meta, category)
        category_boost = _category_boost(base_score, category_status, category_confidence)
        rating_boost = _rating_preference_boost(
            base_score,
            meta["rating"],
            meta["review_count"],
            bool(_structured_plan and _structured_plan.prefer_high_rating),
        )
        score = base_score + category_boost + rating_boost
        distance = None
        if origin_lat is not None and origin_lng is not None and meta["lat"] is not None and meta["lng"] is not None:
            distance = haversine_km(origin_lat, origin_lng, meta["lat"], meta["lng"])

        candidates.append({
            "restaurant_id": restaurant_id,
            "name": _normalize_unicode_text(meta["name"]),
            "category": _normalize_unicode_text(meta["category"]),
            "category_kakao": _normalize_unicode_text(meta["category_kakao"]),
            "description": _normalize_unicode_text(meta["description"]),
            "description_kakao": _normalize_unicode_text(meta["description_kakao"]),
            "rating": meta["rating"],
            "review_count": meta["review_count"],
            "hours": _normalize_unicode_text(meta["hours"]),
            "open_status": open_status,
            "open_status_basis": open_status_basis,
            "address": _normalize_unicode_text(meta["address"]),
            "image": meta["image"],
            "link": meta.get("link"),
            "lat": meta["lat"],
            "lng": meta["lng"],
            "distance_km": distance,
            "has_parking": meta["has_parking"],
            "allows_pets": meta["allows_pets"],
            "has_kids_menu": meta["has_kids_menu"],
            "has_group_seating": meta["has_group_seating"],
            "has_private_room": meta["has_private_room"],
            "has_baby_chair": meta["has_baby_chair"],
            "has_disabled_access": meta["has_disabled_access"],
            "menu_price_min": meta["menu_price_min"],
            "menu_price_median": meta["menu_price_median"],
            "menu_price_lo": meta.get("menu_price_lo"),
            "menu_price_hi": meta.get("menu_price_hi"),
            "score": score,
            "breakdown": {
                "restaurant_rrf": rest_score,
                "review_rrf": review_score,
                "menu_rrf": menu_score,
                "base_score": base_score,
                "category_status": category_status,
                "category_confidence": category_confidence,
                "category_boost": category_boost,
                "rating_preference_boost": rating_boost,
            },
            "evidence": {"reviews": reviews, "menus": menus},
        })

    target_visit_at = _structured_plan.target_visit_at if _structured_plan else None
    # 평점 선호는 score 안의 가산점으로 이미 반영했으므로 정렬 1순위 키로 쓰지 않는다.
    candidates.sort(key=lambda item: (
        0 if not target_visit_at or item["open_status"] is True else 1,
        -item["score"],
        -(item["review_count"] or 0),
        item["restaurant_id"],
    ))
    candidates, category_no_match = _select_by_category(candidates, category)
    candidates = candidates[:top_n]
    include_weather_features = (
        _structured_plan is None or _structured_plan.include_weather_features
    )
    if include_weather_features:
        menu_features = _load_weather_menu_features(
            suffix, [candidate["restaurant_id"] for candidate in candidates]
        )
        for candidate in candidates:
            candidate["weather_features"] = menu_features[candidate["restaurant_id"]]
    return {
        "candidates": candidates,
        "location_name": location_name,
        "origin_lat": origin_lat,
        "origin_lng": origin_lng,
        "extracted_category": category,
        "cleaned_query": semantic_query,
        # 요청한 음식 종류의 후보가 하나도 없었음을 상위 계층이 구분할 수 있게 한다.
        # (빈 결과의 원인이 '지역·조건 부족'인지 '해당 음식 종류 없음'인지 다르다)
        "category_no_match": category_no_match,
        "menu_no_match": False,
        "required_menu_terms": list(
            _structured_plan.required_menu_terms if _structured_plan else ()
        ),
        "location_resolution_failed": False,
    }


def _passes_candidate_filters(
    meta: dict,
    plan: StructuredRestaurantSearchPlan | None,
    *,
    min_rating: float | None,
    open_now: bool,
) -> tuple[bool, bool | None, str | None]:
    """구조화 하드 필터를 한 후보에 적용하고 영업 판정 근거를 함께 반환한다."""
    if plan and not address_matches_search_area(
        plan.search_area_name or plan.location_name, meta.get("address")
    ):
        return False, None, None
    if min_rating is not None and (
        meta.get("rating") is None or meta["rating"] < min_rating
    ):
        return False, None, None
    if plan and any(
        meta.get(field) is not True for field in plan.required_feature_fields
    ):
        return False, None, None
    if plan and any(
        meta.get(field) is True for field in plan.excluded_feature_fields
    ):
        return False, None, None
    if plan and (plan.budget_min_krw is not None or plan.budget_max_krw is not None):
        # menu_price_median은 사이드메뉴에 눌려 비싼 코스를 못 잡으므로, 실제
        # 메뉴 가격 범위(최저~최고)와 예산 범위가 겹치는지로 판단한다.
        # 가격 정보가 전혀 없는 식당은 예산 부합 여부를 추측하지 않고 제외한다.
        price_lo = meta.get("menu_price_lo")
        price_hi = meta.get("menu_price_hi")
        if price_lo is None and price_hi is None:
            return False, None, None
        rest_lo = price_lo if price_lo is not None else price_hi
        rest_hi = price_hi if price_hi is not None else price_lo
        budget_lo = plan.budget_min_krw or 0
        budget_hi = (
            plan.budget_max_krw if plan.budget_max_krw is not None else float("inf")
        )
        if rest_hi < budget_lo or rest_lo > budget_hi:
            return False, None, None

    target_visit_at = plan.target_visit_at if plan else None
    open_status = (
        is_open_at(meta.get("hours"), target_visit_at)
        if target_visit_at
        else is_open_now(meta.get("hours"))
    )
    open_status_basis = (
        "requested_time" if target_visit_at else "now" if open_now else None
    )
    # '현재 영업 중'은 명시적 필터이므로 영업시간 미확인(None)도 통과시키지 않는다.
    if open_now and open_status is not True:
        return False, open_status, open_status_basis
    # 미래 방문 시각에는 확실히 닫힌 후보만 제거하고 미확인 후보는 fallback으로 둔다.
    if target_visit_at and open_status is False:
        return False, open_status, open_status_basis
    return True, open_status, open_status_basis


def search_places(query: str, lang: str = "ko") -> list[Place]:
    result = search_restaurants(query, lang=lang, top_n=30)
    return [
        Place(
            source_type="restaurant",
            source_id=str(candidate["restaurant_id"]),
            name=candidate["name"],
            category=candidate["category"] or "",
            score=candidate["score"],
            reason="RAG 식당·리뷰·메뉴 검색 결과",
            lat=candidate["lat"],
            lng=candidate["lng"],
            rag_score=candidate["score"],
        )
        for candidate in result["candidates"]
    ]
