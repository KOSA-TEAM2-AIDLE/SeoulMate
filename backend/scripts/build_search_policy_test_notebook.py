"""검색 정책·RAG 랭킹 회귀 검증 노트북(SeoulMate_search_policy_test.ipynb)을 생성한다.

DB/OpenAI 없이도 1~7절이 전부 실행된다. 8절만 실제 백엔드가 필요하다.
"""

from __future__ import annotations

import json
from pathlib import Path


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.strip("\n").splitlines(keepends=True)}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.strip("\n").splitlines(keepends=True),
    }


CELLS = [
    md("""
# SeoulMate 검색 정책 회귀 테스트

`query_policy.py` / `rag.py` 의 랭킹·필터 로직이 의도대로 동작하는지 셀 단위로 검증한다.

| 절 | 검증 대상 | 외부 의존 |
|---|---|---|
| 1 | 쿼리 정제 (`_clean_base_query`, `build_semantic_query`) | 없음 |
| 2 | 지역 추론 (`infer_task_location`, `effective_task_filters`) | 없음 |
| 3 | 시설 하드필터 (`explicit_feature_fields`) | 없음 |
| 4 | 날짜·시간·예산·평점 신뢰 정책 | 없음 |
| 5 | **카테고리 부스트가 실제로 순위를 바꾸는가** | 없음 |
| 6 | 날씨 재랭킹이 부스트를 상쇄하지 않는가 | 없음 |
| 7 | 평점 선호 가산점이 관련도를 덮어쓰지 않는가 | 없음 |
| 8 | 실제 DB 스모크 테스트 | **PostgreSQL + OpenAI 키** |

1~7절은 순수 함수만 호출하므로 DB·LLM 없이 바로 돌아간다.
"""),
    md("## 0. 부트스트랩"),
    code("""
import sys
from pathlib import Path

# backend 루트(= services/ 가 있는 디렉터리)를 찾아 sys.path 에 넣는다.
here = Path.cwd()
for base in (here, *here.parents):
    if (base / "services" / "query_policy.py").exists():
        if str(base) not in sys.path:
            sys.path.insert(0, str(base))
        BACKEND_DIR = base
        break
else:
    raise RuntimeError("services/query_policy.py 를 찾지 못했습니다. backend 디렉터리에서 실행하세요.")

print("BACKEND_DIR:", BACKEND_DIR)

RESULTS: list[tuple[str, str, bool]] = []  # (절, 라벨, 통과여부)
SECTION = "0"


def check(label, got, want):
    ok = got == want
    RESULTS.append((SECTION, label, ok))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}")
    if not ok:
        print(f"         got  = {got!r}")
        print(f"         want = {want!r}")
    return ok


def show_rows(rows):
    # pandas 없이도 노트북에서 비교표를 읽기 쉽게 출력한다.
    if not rows:
        print("(행 없음)")
        return
    columns = list(rows[0])
    print(" | ".join(columns))
    print(" | ".join("---" for _ in columns))
    for row in rows:
        print(" | ".join(str(row.get(column, "")) for column in columns))
"""),
    md("""
## 1. 쿼리 정제

`_clean_base_query` 는 원래 `str.strip(" ,|이고이며")` 를 썼다. `strip()` 은 **문자 집합**을 지우므로
`떡볶이 → 떡볶`, `곱창구이 → 곱창구` 처럼 어미가 아닌 글자까지 잘라 임베딩 문장을 망가뜨렸다.

- **회귀 방지**: 음식명이 잘리지 않아야 한다.
- **의도 보존**: 평점/가격 제거 후 앞뒤에 남는 연결어미(`이고`, `이며`)는 여전히 지워야 한다.
"""),
    code("""
SECTION = "1"
from schemas.structured_query import StructuredTravelQuery, StructuredQueryTask
from services.query_policy import build_semantic_query, build_menu_query, effective_task_filters


def make_query(question, search_query=None, location=None, domain="restaurant", themes=None):
    task = StructuredQueryTask(
        task_id="task_1",
        domain=domain,
        search_query=search_query or question,
        themes=themes or [],
    )
    parsed = StructuredTravelQuery(
        intent="single_place_recommendation",
        original_question=question,
        normalized_question=question,
        tasks=[task],
        filters={"location": location} if location else {},
    )
    return parsed, task


print("[의미 쿼리] 지역·평점·가격만 빠지고 음식명은 보존되는가")
cases = [
    # (search_query, location, 기대 의미 쿼리)
    ("홍대 떡볶이 맛집",                    "홍대", "떡볶이 맛집"),        # 회귀: '떡볶' 절단 금지
    ("강남 곱창구이 잘하는 곳",              "강남", "곱창구이 잘하는 곳"),  # 회귀: '곱창구' 절단 금지
    ("홍대 평점 4.5 이상이고 주차 가능한 한식당", "홍대", "주차 가능한 한식당"),  # 의도 보존
    ("강남 5만원 이하이고 조용한 중식당",      "강남", "조용한 중식당"),      # 의도 보존
    ("성수 오이 무침 잘하는 집",             "성수", "오이 무침 잘하는 집"),
]
for search_query, location, want in cases:
    parsed, task = make_query(search_query, location=location)
    filters = effective_task_filters(parsed, task)
    check(f"semantic({search_query})", build_semantic_query(task, filters), want)
"""),
    md("""
## 2. 지역 추론

`effective_task_filters` 는 Task에 지역 필터가 없을 때 `search_query` 에서 지역을 추론한다.

- 기존: **가장 앞에 나온** alias 선택 → `"서울 홍대 조용한 카페"` 가 **`서울`** 로 판정되어
  시청 좌표 + 반경 2km 로 검색 → 홍대(약 5km) 후보가 통째로 사라졌다.
- 수정: **구체 지역 > 접미사 토큰(역/동/시장/공원) > 광역 지역** 순으로 선택.
- 다중 Task 질문에서 미등록 지역이 전역 필터를 **조용히 상속**하던 문제도 함께 검증한다.
"""),
    code("""
SECTION = "2"
from services.query_policy import infer_task_location

print("[단일 추론] 구체 지역이 광역 지역을 이기는가")
for search_query, want in [
    ("서울 홍대 조용한 카페",   "홍대"),   # 회귀: '서울'로 오인 금지
    ("서울 강남 파스타집",      "강남"),
    ("서울에서 성수 감성 카페",  "성수"),
    ("홍대 조용한 카페",        "홍대"),
    ("역삼동 조용한 카페",      "역삼동"),  # alias 미등록 → 접미사 토큰으로 인식
    ("강남역 근처 한식당",      "강남"),
    ("서울 맛집 추천",          "서울"),   # 구체 지역이 없을 때만 광역 허용
    ("운동하고 먹을 식당",       None),    # 오탐 금지
    ("친구랑 갈 식당",          None),    # 오탐 금지
    ("조용한 카페",             None),
]:
    check(f"infer({search_query})", infer_task_location(search_query), want)

print()
print("[다중 Task] 전역 지역을 다른 지역 Task가 상속하면 안 된다")
task_restaurant = StructuredQueryTask(task_id="t1", domain="restaurant", search_query="홍대 조용한 식당")
task_cafe = StructuredQueryTask(task_id="t2", domain="cafe", search_query="역삼동 분위기 좋은 카페")
parsed = StructuredTravelQuery(
    intent="day_trip_route",
    original_question="홍대에서 식당, 역삼동에서 카페 추천해줘",
    normalized_question="홍대 식당, 역삼동 카페 추천",
    tasks=[task_restaurant, task_cafe],
    filters={"location": "홍대"},
)
check("restaurant task location", effective_task_filters(parsed, task_restaurant).location, "홍대")
check("cafe task location",       effective_task_filters(parsed, task_cafe).location,       "역삼동")
"""),
    md("""
## 3. 시설 하드필터

`explicit_feature_fields` 결과는 **해당 컬럼이 `True` 인 가게만 통과**시키는 하드 필터다.
따라서 오탐 비용이 매우 크다.

기존에는 짧고 다의적인 부분 문자열을 그대로 썼다.
- `accessible` → *"easily accessible from Hongdae Station"* 이 `has_disabled_access` 로 오인
- `groups` → *"in groups of friends"* 가 `has_group_seating` 로 오인
- `룸` → *"플레이룸"* 이 `has_private_room` 으로 오인

수정 후에는 단어 경계·문맥을 갖춘 패턴만 인정한다. **정탐은 유지되어야 한다.**
"""),
    code("""
SECTION = "3"
from services.query_policy import explicit_feature_fields, structured_feature_fields


def features_of(question):
    parsed, _ = make_query(question)
    return explicit_feature_fields(parsed)


print("[오탐] 시설 조건이 아닌데 걸리면 안 되는 문장")
for question, want in [
    ("Find a cafe easily accessible from Hongdae Station.", ()),
    ("Any restaurant in groups of friends style, casual vibe?", ()),
    ("홍대 플레이룸 근처 조용한 식당", ()),
    ("주차는 없어도 괜찮아. 평점 좋은 태국 음식점 추천해줘.", ()),   # 선택 조건 → 필터 아님
    ("반려동물 안 되는 곳 말고 다른 데 추천해줘", ()),               # 부정 표현
]:
    check(f"features({question[:38]})", features_of(question), want)

print()
print("[정탐] 실제 시설 조건은 반드시 잡혀야 한다")
for question, want in [
    ("주차 가능한 한식당", ("has_parking",)),
    ("Wheelchair accessible Chinese restaurant", ("has_disabled_access",)),
    ("룸 있는 중식당 추천해줘", ("has_private_room",)),
    ("단체석 있는 고깃집", ("has_group_seating",)),
    ("반려동물 동반 가능한 카페", ("allows_pets",)),
    ("유아 의자 있는 브런치 식당", ("has_baby_chair",)),
]:
    check(f"features({question[:38]})", features_of(question), want)

print()
check("structured(['주차','휠체어'])",
      structured_feature_fields(["주차", "휠체어"]),
      ("has_parking", "has_disabled_access"))
"""),
    md("""
## 4. 날짜·시간·예산·평점 신뢰 정책

GPT 파서가 만든 구조화 필드는 **원문에 실제 근거가 있을 때만** 채택한다.
근거 없는 필드를 그대로 믿으면 환각이 하드 필터로 굳어진다.
"""),
    code("""
SECTION = "4"
from datetime import date, datetime
from services.query_policy import (
    derive_source_mode,
    extract_min_rating,
    prefers_high_rating,
    target_visit_datetime,
    trusted_budget_bounds,
    trusted_radius_km,
    trusted_time_window,
    trusted_visit_date,
)

TODAY = date(2026, 7, 14)  # 테스트 고정 기준일 (화요일)

print("[날짜] 원문의 명시적 표현으로 파서 날짜를 교정")
for question, want in [
    ("내일 저녁에 갈 식당 추천해줘", date(2026, 7, 15)),
    ("모레 점심 식당 추천해줘",     date(2026, 7, 16)),
    ("오늘 저녁 식당 추천해줘",     date(2026, 7, 14)),
    ("7월 20일에 갈 식당 추천해줘", date(2026, 7, 20)),
]:
    parsed, _ = make_query(question)
    check(f"visit_date({question[:16]})", trusted_visit_date(parsed, today=TODAY), want)

print()
print("[시간] 원문에 시간 표현이 없으면 GPT의 time_window를 쓰지 않는다")
parsed_no_time, _ = make_query("조용한 중식당 추천해줘")
parsed_no_time.filters.time_window = "저녁"   # 파서가 근거 없이 채운 값
check("근거 없는 time_window는 무시", trusted_time_window(parsed_no_time), None)

parsed_time, _ = make_query("저녁에 갈 조용한 중식당 추천해줘")
parsed_time.filters.time_window = "저녁"
check("근거 있는 time_window는 채택", trusted_time_window(parsed_time), "저녁")

print()
print("[예산] 원문에 금액 표현이 없으면 예산 필터를 쓰지 않는다")
parsed_no_budget, _ = make_query("조용한 중식당 추천해줘")
parsed_no_budget.filters.budget_max_krw = 30000   # 근거 없는 값
check("근거 없는 예산은 무시", trusted_budget_bounds(parsed_no_budget), (None, None))

parsed_budget, _ = make_query("5만원 이하 중식당 추천해줘")
parsed_budget.filters.budget_max_krw = 50000
check("근거 있는 예산은 채택", trusted_budget_bounds(parsed_budget), (None, 50000))

print()
print("[평점] 명시 평점은 하드 필터, 모호한 선호는 가산점 플래그")
parsed_rating, _ = make_query("평점 4.5 이상인 한식당 추천해줘")
check("min_rating 추출", extract_min_rating(parsed_rating), 4.5)
check("명시 평점은 선호 플래그가 아님", prefers_high_rating(parsed_rating), False)

parsed_prefer, _ = make_query("평점 좋은 태국 음식점 추천해줘")
check("모호한 선호 → 가산점 플래그", prefers_high_rating(parsed_prefer), True)
check("모호한 선호 → 하드 필터 없음", extract_min_rating(parsed_prefer), None)

print()
print("[반경 / 실행 모드]")
parsed_radius, _ = make_query("강남역 반경 3km 안에서 한식당 추천해줘")
check("명시 반경 채택", trusted_radius_km(parsed_radius), 3.0)
parsed_default, _ = make_query("강남역 한식당 추천해줘")
check("반경 미명시 → 기본값", trusted_radius_km(parsed_default), 2.0)

parsed_rag, _ = make_query("조용한 중식당 추천해줘")
check("Task만 있고 날짜/날씨 없음 → rag_only", derive_source_mode(parsed_rag), "rag_only")
parsed_ragmcp, _ = make_query("내일 저녁 조용한 중식당 추천해줘")
check("날짜 있음 → rag_mcp", derive_source_mode(parsed_ragmcp), "rag_mcp")
"""),
    md("""
## 5. 카테고리 부스트 (핵심)

`extract_category` 가 잡은 음식 종류는 반드시 랭킹에 반영되어야 한다.

**기존 구현이 무효였던 이유**
1. `mismatch` 후보는 어차피 전량 제외 → 감점할 대상이 없다.
2. 살아남은 후보는 전원 같은 `match` → **전원 같은 배율**을 받아 상대 순서가 그대로다.

**수정 방향** — `match` 를 신뢰도로 등급화해 부스트를 non-uniform 하게 만든다.

| status / confidence | 근거 | 부스트 |
|---|---|---|
| `match` / `confirmed` | `category_kakao` 로 확정 | `CATEGORY_BOOST_PCT` (+20%) |
| `match` / `inferred` | 혼합되기 쉬운 원본 `category` 태그로 추정 | `CATEGORY_INFERRED_BOOST_PCT` (+8%) |
| `mismatch` | 다른 음식군으로 확인 | **제외** (감점 아님) |
| `no_data` | 어떤 음식군에도 매핑 불가 | recall 용 폴백 |

역전 임계값 = `1.20 / 1.08 ≈ 1.111` → 추정 일치가 확정 일치를 이기려면 base 점수가 11% 이상 높아야 한다.
"""),
    code("""
SECTION = "5"
from services.rag import (
    CATEGORY_BOOST_PCT,
    CATEGORY_INFERRED_BOOST_PCT,
    _category_boost,
    _category_match_status,
    _select_by_category,
    extract_category,
)

print(f"상수: confirmed=+{CATEGORY_BOOST_PCT:.0%}, inferred=+{CATEGORY_INFERRED_BOOST_PCT:.0%}, "
      f"역전 임계 base 비율={1 + CATEGORY_BOOST_PCT:.2f}/{1 + CATEGORY_INFERRED_BOOST_PCT:.2f} "
      f"= {(1 + CATEGORY_BOOST_PCT) / (1 + CATEGORY_INFERRED_BOOST_PCT):.3f}")
print()

print("[카테고리 추출]")
check("중식당 → 중국 요리", extract_category("홍대 조용한 중식당")[0], "중국 요리")
check("Chinese restaurant → 중국 요리", extract_category("quiet chinese restaurant", "en")[0], "중국 요리")

print()
print("[status / confidence 판정]")
check("카카오=중국 요리 → 확정 일치",
      _category_match_status({"category_kakao": "중국 요리", "category": "음식점"}, "중국 요리"),
      ("match", "confirmed"))
check("카카오 없음 + 원본태그=중식 → 추정 일치",
      _category_match_status({"category_kakao": None, "category": "중식, 음식점"}, "중국 요리"),
      ("match", "inferred"))
check("카카오=한식 → 불일치",
      _category_match_status({"category_kakao": "한식", "category": "중식"}, "중국 요리"),
      ("mismatch", "confirmed"))
check("매핑 불가 태그 → no_data",
      _category_match_status({"category_kakao": None, "category": "음식점"}, "중국 요리"),
      ("no_data", None))
"""),
    code("""
SECTION = "5"

# base 점수는 '추정 중식당 B' 가 더 높다. 부스트가 없으면 B가 1위가 된다.
POOL = [
    {"name": "확정 중식당 A", "base": 0.0220, "status": "match",    "confidence": "confirmed"},
    {"name": "추정 중식당 B", "base": 0.0230, "status": "match",    "confidence": "inferred"},
    {"name": "확정 한식당 C", "base": 0.0400, "status": "mismatch", "confidence": "confirmed"},
    {"name": "분류없음 D",    "base": 0.0180, "status": "no_data",  "confidence": None},
]


def rank_pool(use_boost: bool):
    rows = []
    for item in POOL:
        boost = _category_boost(item["base"], item["status"], item["confidence"]) if use_boost else 0.0
        rows.append({
            "restaurant_id": item["name"],
            "name": item["name"],
            "base_score": item["base"],
            "category_boost": boost,
            "score": item["base"] + boost,
            "review_count": 0,
            "breakdown": {"category_status": item["status"], "category_confidence": item["confidence"]},
        })
    rows.sort(key=lambda r: (-r["score"], -(r["review_count"] or 0), r["restaurant_id"]))
    selected, no_match = _select_by_category(rows, "중국 요리")
    return selected, no_match


off, _ = rank_pool(use_boost=False)
on, no_match = rank_pool(use_boost=True)

show_rows([
    {
        "순위": i + 1,
        "부스트 OFF": off[i]["name"] if i < len(off) else "-",
        "OFF 점수": round(off[i]["score"], 5) if i < len(off) else None,
        "부스트 ON": on[i]["name"] if i < len(on) else "-",
        "ON 점수": round(on[i]["score"], 5) if i < len(on) else None,
    }
    for i in range(max(len(off), len(on)))
])

check("부스트 OFF → base 높은 '추정 B'가 1위", off[0]["name"], "추정 중식당 B")
check("부스트 ON  → '확정 A'가 역전해 1위",   on[0]["name"],  "확정 중식당 A")
check("mismatch(한식당)는 base가 최고여도 제외", [r["name"] for r in on], ["확정 중식당 A", "추정 중식당 B"])
check("최종 후보는 전부 match (기존 감사 불변식 유지)",
      all(r["breakdown"]["category_status"] == "match" for r in on), True)
check("match 없으면 no_data 폴백",
      [r["name"] for r in _select_by_category([r for r in on if False] + [
          {"restaurant_id": "D", "name": "분류없음 D", "score": 0.018,
           "breakdown": {"category_status": "no_data"}}], "중국 요리")[0]],
      ["분류없음 D"])
check("전부 mismatch → 빈 결과 + no_match 플래그",
      _select_by_category([{"restaurant_id": "C", "breakdown": {"category_status": "mismatch"}}], "중국 요리"),
      ([], True))
"""),
    md("""
## 6. 날씨 재랭킹이 부스트를 상쇄하지 않는가

`weather_reranker.rerank_with_weather` 는 `rag_normalized = raw_score / high` 로 **최고점 정규화**를 한다.
따라서 모든 후보에 **균일한** 배율을 곱하면 하류에서 완전히 상쇄된다.
(= 기존 부스트가 무효였던 두 번째 이유)

등급이 다른 부스트는 정규화 후에도 살아남아야 한다.
"""),
    code("""
SECTION = "6"

boosted_a = 0.0220 * (1 + CATEGORY_BOOST_PCT)           # 확정 일치
boosted_b = 0.0230 * (1 + CATEGORY_INFERRED_BOOST_PCT)  # 추정 일치
high = max(boosted_a, boosted_b)
print(f"확정 A 정규화 점수: {boosted_a / high:.4f}")
print(f"추정 B 정규화 점수: {boosted_b / high:.4f}")
check("정규화 후에도 확정 일치가 우위", boosted_a > boosted_b, True)

# 대조군: 균일 배율은 정규화에서 완전히 사라진다 (기존 구현의 실패 재현)
uniform_a, uniform_b = 0.0220 * 1.20, 0.0230 * 1.20
uniform_high = max(uniform_a, uniform_b)
check("균일 배율은 정규화 후 원본과 동일 (부스트 무효 재현)",
      (round(uniform_a / uniform_high, 6), round(uniform_b / uniform_high, 6)),
      (round(0.0220 / 0.0230, 6), 1.0))

# 실제 재랭커로도 확인 (core.config 가 필요하므로 실패해도 넘어간다)
try:
    from services.weather_reranker import rerank_with_weather

    candidates = [
        {"restaurant_id": 1, "name": "확정 중식당 A", "score": boosted_a, "distance_km": 0.3,
         "description": "", "description_kakao": "", "has_parking": True, "weather_features": {}},
        {"restaurant_id": 2, "name": "추정 중식당 B", "score": boosted_b, "distance_km": 0.3,
         "description": "", "description_kakao": "", "has_parking": True, "weather_features": {}},
    ]
    weather = {"available": True, "condition": "clear", "temperature_c": 22, "wind_speed_mps": 2.0}
    ranked = rerank_with_weather(candidates, weather, "조용한 중식당 추천", source_mode="rag_mcp")
    print()
    print("재랭킹 후 순서:", [c["name"] for c in ranked])
    check("날씨 재랭킹 후에도 확정 일치가 1위", ranked[0]["name"], "확정 중식당 A")
except Exception as exc:  # core.config 미설정 등
    print(f"(건너뜀) weather_reranker 로드 실패: {type(exc).__name__}: {exc}")
"""),
    md("""
## 7. 평점 선호 가산점

`prefer_high_rating` 은 *"평점 좋은 곳"* 같은 **모호한 선호** 표현에서만 켜진다.
이걸 정렬 1순위 키로 쓰면 **리뷰 2개짜리 5.0점 신규 가게**가 최적합 후보를 이겨버린다.

수정: 유계 가산점으로 전환하고, **리뷰 수가 적으면 신뢰도를 낮춰** 가산점도 줄인다.
"""),
    code("""
SECTION = "7"
from services.rag import _rating_preference_boost

CANDS = [
    {"restaurant_id": 1, "name": "관련도 최상 인기집", "base": 0.0400, "rating": 4.4, "reviews": 1200},
    {"restaurant_id": 2, "name": "관련도 중간",        "base": 0.0200, "rating": 4.6, "reviews": 300},
    {"restaurant_id": 3, "name": "관련도 최하 신규집", "base": 0.0010, "rating": 5.0, "reviews": 2},
]


def rank_rating(prefer: bool):
    rows = []
    for c in CANDS:
        boost = _rating_preference_boost(c["base"], c["rating"], c["reviews"], prefer)
        rows.append({**c, "boost": boost, "score": c["base"] + boost})
    rows.sort(key=lambda r: (-r["score"], -(r["reviews"] or 0), r["restaurant_id"]))
    return rows


on = rank_rating(True)
show_rows([
    {"순위": i + 1, "이름": r["name"], "평점": r["rating"], "리뷰수": r["reviews"],
     "base": round(r["base"], 5), "평점 가산점": round(r["boost"], 6), "최종": round(r["score"], 5)}
    for i, r in enumerate(on)
])

check("평점 선호 시에도 관련도 최상이 1위", on[0]["name"], "관련도 최상 인기집")
check("리뷰 2개 5.0점은 여전히 꼴찌",       on[-1]["name"], "관련도 최하 신규집")
check("리뷰 부족 후보의 가산점은 신뢰도로 축소",
      _rating_preference_boost(0.02, 5.0, 2, True) < _rating_preference_boost(0.02, 5.0, 300, True), True)
check("선호 플래그가 꺼지면 가산점 0", _rating_preference_boost(0.02, 5.0, 300, False), 0.0)
"""),
    md("""
## 8. (선택) 실제 DB 스모크 테스트

PostgreSQL + OpenAI 키가 있을 때만 실행된다. 실제 `search_restaurants_structured` 를 호출해
- 반경 밖 후보가 섞이지 않는지
- 요청한 음식 종류와 다른 후보(`mismatch`)가 나오지 않는지
- 필수 시설 조건이 실제로 걸러지는지
를 확인한다.
"""),
    code("""
SECTION = "8"
import os

try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except Exception:
    pass

HAS_BACKEND = bool(os.getenv("OPENAI_API_KEY"))
if HAS_BACKEND:
    import socket
    from core.config import DB_CONFIG
    try:
        with socket.create_connection(
            (DB_CONFIG.get("host", "localhost"), int(DB_CONFIG.get("port", 5432))),
            timeout=1.0,
        ):
            pass
    except OSError as exc:
        HAS_BACKEND = False
        print(f"PostgreSQL 연결 불가로 실제 DB 테스트를 건너뜁니다: {exc}")
if not HAS_BACKEND:
    print("실제 DB 테스트 조건이 없어 건너뜁니다. (1~7절만으로도 로직 검증은 완료)")
else:
    from services.rag import build_restaurant_search_plan, search_restaurants_structured

    parsed, task = make_query(
        "홍대에서 주차 가능한 조용한 중식당 추천해줘",
        search_query="홍대 조용한 중식당",
        location="홍대",
    )
    plan = build_restaurant_search_plan(parsed, task, current_lat=37.5665, current_lng=126.9780)
    print("PLAN:")
    for key, value in plan.__dict__.items():
        print(f"  {key:26} = {value!r}")

    result = search_restaurants_structured(parsed, task, current_lat=37.5665, current_lng=126.9780, top_n=10)
    candidates = result["candidates"]
    print(f"\\n후보 {len(candidates)}건 / category_no_match={result.get('category_no_match')}")

    show_rows([
        {
            "순위": i + 1,
            "이름": c["name"],
            "카테고리": c.get("category_kakao") or c.get("category"),
            "status": c["breakdown"]["category_status"],
            "confidence": c["breakdown"].get("category_confidence"),
            "base": round(c["breakdown"]["base_score"], 5),
            "카테고리부스트": round(c["breakdown"].get("category_boost") or 0, 6),
            "최종점수": round(c["score"], 5),
            "거리km": None if c["distance_km"] is None else round(c["distance_km"], 2),
            "주차": c.get("has_parking"),
        }
        for i, c in enumerate(candidates)
    ])

    check("반경 밖 후보 없음",
          all(c["distance_km"] is None or c["distance_km"] <= plan.radius_km + 0.01 for c in candidates), True)
    check("음식 종류 불일치 후보 없음",
          all(c["breakdown"]["category_status"] != "mismatch" for c in candidates), True)
    if "has_parking" in plan.required_feature_fields:
        check("주차 필수 조건이 실제로 걸러짐",
              all(c.get("has_parking") is True for c in candidates), True)
"""),
    md("## 9. 결과 요약"),
    code("""
from collections import defaultdict

section_counts = defaultdict(lambda: {"통과": 0, "전체": 0})
for section, _label, ok in RESULTS:
    section_counts[section]["전체"] += 1
    section_counts[section]["통과"] += int(ok)
show_rows([
    {"절": section, **counts, "실패": counts["전체"] - counts["통과"]}
    for section, counts in sorted(section_counts.items())
])

failures = [(section, label) for section, label, ok in RESULTS if not ok]
if failures:
    print(f"\\n실패 {len(failures)}건:")
    show_rows([{"절": section, "항목": label} for section, label in failures])
else:
    print(f"\\n전체 {len(RESULTS)}건 모두 통과")

assert len(failures) == 0, f"{len(failures)}건 실패"
"""),
]


NOTEBOOK = {
    "cells": CELLS,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


def main() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    path = backend_dir / "notebooks" / "SeoulMate_search_policy_test.ipynb"
    path.write_text(json.dumps(NOTEBOOK, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"생성 완료: {path}  (셀 {len(CELLS)}개)")


if __name__ == "__main__":
    main()
