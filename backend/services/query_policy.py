"""고정 Structured Query를 RAG/MCP 실행 계획으로 변환한다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from schemas.structured_query import (
    StructuredQueryTask,
    StructuredSearchFilters,
    StructuredTravelQuery,
)
from core.language import detect_input_language


ExecutionMode = Literal["rag_only", "rag_mcp", "mcp_only", "general"]


def _task_deduplication_key(
    parsed: StructuredTravelQuery,
    task: StructuredQueryTask,
) -> tuple:
    """동일 요청을 복제한 GPT Task만 찾고, 같은 도메인의 다른 요구는 보존한다."""
    normalized_query = re.sub(
        r"[^0-9a-z가-힣]+", " ", task.search_query.casefold()
    ).strip()
    normalized_notes = re.sub(
        r"\s+", " ", (task.notes or "").casefold()
    ).strip()
    # Task에 직접 쓴 홍대와 전역 filters에서 상속한 홍대는 실행 조건이 같다.
    # 원시 task.filters가 아니라 실제 검색에 쓰이는 병합 필터로 비교한다.
    filters = effective_task_filters(parsed, task).model_dump(
        mode="json", exclude_none=True
    )
    return (
        task.domain,
        normalized_query,
        normalized_notes,
        repr(filters),
        task.slot_id,
        task.day_number,
        task.visit_date,
        task.start_time,
        task.end_date,
        task.end_time,
    )


def deduplicate_recommendation_tasks(
    parsed: StructuredTravelQuery,
) -> StructuredTravelQuery:
    """비루트 요청에서 파서가 완전히 같은 Task를 반복 생성한 경우만 병합한다."""
    if parsed.intent in {"day_trip_route", "multi_day_route"}:
        return parsed
    if len(parsed.tasks) < 2:
        return parsed

    deduplicated: list[StructuredQueryTask] = []
    index_by_key: dict[tuple, int] = {}
    for task in parsed.tasks:
        key = _task_deduplication_key(parsed, task)
        existing_index = index_by_key.get(key)
        if existing_index is None:
            index_by_key[key] = len(deduplicated)
            deduplicated.append(task)
            continue

        existing = deduplicated[existing_index]
        merged_themes = list(dict.fromkeys([*existing.themes, *task.themes]))
        deduplicated[existing_index] = existing.model_copy(update={
            "themes": merged_themes,
            "desired_count": max(existing.desired_count, task.desired_count),
        })

    # GPT가 날씨 조건을 장소 요구로 다시 풀어 같은 도메인 Task를 복제하는 경우를
    # 한 번 더 정리한다. 명시적으로 "각각"을 요구한 경우는 건드리지 않는다.
    explicit_split = bool(re.search(
        r"(?:각각|각기|each|respectively)", parsed.original_question, re.IGNORECASE
    ))
    if not explicit_split and len(deduplicated) > 1:
        weather_merged: list[StructuredQueryTask] = []
        for task in deduplicated:
            task_has_weather = any(
                word in task.search_query.casefold() for word in WEATHER_WORDS
            )
            merge_index = None
            if task_has_weather:
                task_filters = effective_task_filters(parsed, task).model_dump(
                    mode="json", exclude_none=True
                )
                for index, existing in enumerate(weather_merged):
                    if existing.domain != task.domain:
                        continue
                    existing_filters = effective_task_filters(
                        parsed, existing
                    ).model_dump(mode="json", exclude_none=True)
                    if existing_filters == task_filters:
                        merge_index = index
                        break
            if merge_index is None:
                weather_merged.append(task)
                continue
            existing = weather_merged[merge_index]
            weather_merged[merge_index] = existing.model_copy(update={
                "themes": list(dict.fromkeys([*existing.themes, *task.themes])),
                "desired_count": max(existing.desired_count, task.desired_count),
            })
        deduplicated = weather_merged

    if len(deduplicated) == len(parsed.tasks):
        return parsed
    return parsed.model_copy(update={"tasks": deduplicated})

# 구체 지역과 광역 지역을 분리한다. "서울 홍대 카페"처럼 두 개가 함께 나오면 반드시
# 구체 지역을 골라야 한다. 광역 지역으로 지오코딩하면 기본 반경(2km) 안에 목표
# 상권이 들어오지 않아 후보가 통째로 사라진다.
SPECIFIC_LOCATION_ALIASES = (
    "홍대", "강남", "종로", "성수", "이태원", "잠실", "여의도", "명동",
    "신촌", "광화문", "마포", "을지로", "익선동", "연남동", "압구정",
    "청담", "건대", "합정", "망원", "서촌", "북촌", "동대문",
    "hongdae", "gangnam", "jongno", "seongsu", "itaewon", "jamsil",
    "yeouido", "myeongdong", "sinchon", "gwanghwamun",
)
BROAD_LOCATION_ALIASES = ("서울", "seoul")
TASK_LOCATION_ALIASES = SPECIFIC_LOCATION_ALIASES + BROAD_LOCATION_ALIASES

# alias 목록에 없는 지역(역삼동, 판교역 등)을 다중 Task 질문에서 전역 필터로 잘못
# 상속하지 않도록, 행정구역·역명 접미사를 가진 토큰을 보조로 인식한다.
GENERIC_LOCATION_RE = re.compile(r"([가-힣]{2,6}(?:역|동|시장|공원))(?![가-힣])")
GENERIC_LOCATION_STOPWORDS = frozenset({
    "운동", "이동", "활동", "자동", "공동", "행동", "감동", "작동", "노동",
    "합동", "출동", "회동", "지역", "구역", "영역", "면역", "역할", "병역",
})
LOCATIVE_MARKERS = ("에서", "에", "근처", "인근", "주변", "일대", "쪽")

WEATHER_WORDS = {
    "날씨", "비", "눈", "기온", "온도", "더위", "추위", "바람", "강풍",
    "weather", "rain", "snow", "temperature", "hot", "cold", "wind",
}
LOW_CONGESTION_WORDS = {
    "한적", "덜 붐", "붐비지", "혼잡하지",
    "low congestion", "less crowded", "not crowded",
}


def _has_locative_marker(text: str, end: int) -> bool:
    tail = text[end:].lstrip()
    return any(tail.startswith(marker) for marker in LOCATIVE_MARKERS)


def infer_task_location(search_query: str) -> str | None:
    """Task 문장에서 지역을 추론한다. 구체 지역 > 접미사 토큰 > 광역 지역 순."""
    lowered = search_query.lower()
    # '서울 홍대'처럼 겹칠 때 가장 앞이 아니라 가장 구체적인(=긴) 지역을 고른다.
    specific = [alias for alias in SPECIFIC_LOCATION_ALIASES if alias.lower() in lowered]
    if specific:
        return max(specific, key=lambda alias: (len(alias), -lowered.find(alias.lower())))

    for match in GENERIC_LOCATION_RE.finditer(search_query):
        token = match.group(1)
        if token in GENERIC_LOCATION_STOPWORDS:
            continue
        # 오탐을 줄이기 위해 문장 앞이거나 장소 조사가 뒤따를 때만 지역으로 본다.
        if match.start() == 0 or _has_locative_marker(search_query, match.end()):
            return token

    broad = [alias for alias in BROAD_LOCATION_ALIASES if alias.lower() in lowered]
    return broad[0] if broad else None


def effective_task_filters(
    parsed: StructuredTravelQuery,
    task: StructuredQueryTask,
) -> StructuredSearchFilters:
    """전역 필터 위에 해당 Task의 명시 필터만 덮어쓴다."""
    updates = {
        key: value
        for key, value in (task.filters or StructuredSearchFilters()).model_dump(
            exclude_unset=True,
            exclude_none=True,
        ).items()
        if value != [] and value != ""
    }
    if not updates.get("location"):
        inferred = infer_task_location(task.search_query)
        if inferred:
            updates["location"] = inferred
    if not updates:
        return parsed.filters
    return parsed.filters.model_copy(update=updates)
NOW_WORDS = {"지금", "현재", "바로", "now", "currently", "right now"}
RADIUS_RE = re.compile(r"(?:반경\s*)?(\d+(?:\.\d+)?)\s*(?:km|킬로미터|킬로)", re.IGNORECASE)
RATING_RE = re.compile(
    r"(?:평점|별점|rating|star\s+rating|rated)\s*(?:은|이|가|:)?\s*"
    r"(\d(?:\.\d+)?)\s*(?:점|이상|or higher|and above|\+)?",
    re.IGNORECASE,
)
HIGH_RATING_PREFERENCE_RE = re.compile(
    r"(?:평점|별점)(?:이|은|이\s*)?\s*(?:좋|높)|"
    r"(?:highly|well|best)[-\s]?rated|good\s+(?:rating|reviews?)",
    re.IGNORECASE,
)
TIME_WORDS = {
    "아침", "점심", "저녁", "밤", "오전", "오후", "morning", "lunch",
    "noon", "afternoon", "evening", "dinner", "night", "am", "pm",
}
# 시설 조건은 '해당 컬럼이 True인 가게만 통과'시키는 하드 필터이므로 오탐 비용이 크다.
# 'accessible'(역에서 가까운), 'groups'(친구들끼리), '룸'(플레이룸) 같은 짧고 다의적인
# 부분 문자열을 그대로 쓰지 않고, 단어 경계와 문맥을 갖춘 패턴만 인정한다.
FEATURE_PATTERNS: dict[str, tuple[str, ...]] = {
    "has_parking": (r"주차", r"\bparking\b"),
    "allows_pets": (
        r"반려동물", r"애견", r"강아지", r"펫\s*프렌들리",
        r"pet[-\s]?friendly", r"\bpets?\b",
    ),
    "has_kids_menu": (
        r"키즈\s*메뉴", r"어린이\s*메뉴", r"아이\s*메뉴",
        r"\bkids?[-\s]?menu\b", r"\bchildren'?s\s+menu\b",
    ),
    "has_group_seating": (
        r"단체석", r"단체\s*좌석", r"단체\s*이용", r"단체\s*예약", r"단체\s*회식", r"단체로",
        r"\bgroup\s+seating\b", r"\blarge\s+groups?\b", r"\bbig\s+groups?\b",
        r"\bfor\s+a\s+group\s+of\b",
    ),
    "has_private_room": (
        # '플레이룸', '룸메이트'처럼 다른 단어에 붙은 '룸'은 제외한다.
        r"(?<![가-힣])룸(?=(?:이|은|는|을|를|과|와|도|에|의|으로)?(?:\s|$|[,.;!?]))",
        r"개별실", r"별실", r"프라이빗\s*룸", r"독립\s*공간",
        r"\bprivate\s+room\b", r"\bprivate\s+dining\b",
    ),
    "has_baby_chair": (
        r"아기\s*의자", r"유아\s*의자", r"\bbaby\s*chair\b", r"\bhigh\s*chair\b",
    ),
    "has_disabled_access": (
        r"장애인", r"휠체어", r"무장애", r"배리어\s*프리",
        r"\bwheelchair\b", r"\bdisabled\s+access\b",
        r"\bbarrier[-\s]?free\b", r"\bstep[-\s]?free\b",
    ),
}
# 하위 호환: 기존 이름을 참조하는 코드가 있어도 깨지지 않게 유지한다.
FEATURE_KEYWORDS = FEATURE_PATTERNS


def _feature_matches(text: str, patterns: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)
TIME_WINDOW_HOURS = {
    "아침": 9, "morning": 9,
    "점심": 12, "lunch": 12, "noon": 12,
    "오후": 15, "afternoon": 15,
    "저녁": 19, "evening": 19, "dinner": 19,
    "밤": 21, "night": 21,
}
FUTURE_DATE_WORDS = {
    "오늘", "내일", "모레", "이번 주", "이번주", "다음 주", "다음주",
    "today", "tomorrow", "day after tomorrow", "this week", "next week",
}
WEEKDAY_INDEX = {
    "월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3,
    "금요일": 4, "토요일": 5, "일요일": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
OPTIONAL_FEATURE_PATTERNS = (
    "없어도", "없어도 돼", "상관없", "괜찮", "필수 아니",
    "not required", "don't need", "do not need", "optional", "is fine",
)
NEGATIVE_FEATURE_PATTERNS = (
    "없는", "제외", "불가", "금지", "안 되는", "안되는",
    "no ", "without ", "not allowed", "exclude",
)
CURRENCY_RE = re.compile(
    r"(?:\d[\d,]*(?:\.\d+)?\s*(?:만\s*)?원|₩\s*\d[\d,]*|\b\d[\d,]*\s*won\b)",
    re.IGNORECASE,
)


def _query_text(parsed: StructuredTravelQuery) -> str:
    parts = [parsed.original_question, parsed.normalized_question]
    for task in parsed.tasks:
        parts.extend([task.search_query, *task.themes, task.notes or ""])
    return " ".join(parts).lower()


def derive_source_mode(parsed: StructuredTravelQuery) -> ExecutionMode:
    """프롬프트에 source_mode가 없어도 날짜·Task·날씨 표현으로 실행 모드를 결정한다."""
    text = _query_text(parsed)
    has_weather_signal = any(word in text for word in WEATHER_WORDS)
    has_explicit_date_signal = (
        any(word in text for word in FUTURE_DATE_WORDS)
        or any(word in text for word in WEEKDAY_INDEX)
        or bool(re.search(r"\b20\d{2}[-./]\d{1,2}[-./]\d{1,2}\b", text))
        or bool(re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일", text))
    )
    has_visit_time = bool(
        parsed.filters.start_date
        or parsed.filters.end_date
        or parsed.filters.time_window
    )
    has_rag_tasks = bool(parsed.tasks)
    has_attraction_congestion_signal = (
        any(task.domain == "attraction" for task in parsed.tasks)
        and any(word in text for word in LOW_CONGESTION_WORDS)
    )

    # 상위 GPT가 명시적 날짜/날씨를 놓친 경우에만 안전하게 RAG_MCP로 올린다.
    if parsed.source_mode:
        if (
            parsed.source_mode == "rag_only"
            and has_rag_tasks
            and (
                has_weather_signal
                or has_explicit_date_signal
                or has_attraction_congestion_signal
            )
        ):
            return "rag_mcp"
        return parsed.source_mode

    if has_rag_tasks:
        # 원문에 '내일'처럼 명시적 날짜가 있는데 GPT가 filters.start_date/time_window를
        # 빠뜨린 경우에도 RAG_MCP로 올린다. trusted_visit_date()는 어차피 원문에서
        # 날짜를 복구하므로, 여기서만 파서 필터를 믿으면 '미래 시각으로 영업시간은
        # 거르면서 그 시각 날씨는 보지 않는' 불일치가 생긴다.
        if (
            has_visit_time
            or has_weather_signal
            or has_explicit_date_signal
            or has_attraction_congestion_signal
        ):
            return "rag_mcp"
        return "rag_only"
    if has_weather_signal or parsed.intent == "weather_information":
        return "mcp_only"
    return "general"


def should_filter_open_now(
    parsed: StructuredTravelQuery,
    filters: StructuredSearchFilters,
) -> bool:
    """미래 방문을 현재 영업 여부로 잘못 거르지 않을 때만 open_now를 켠다."""
    if filters.is_active is not True:
        return False
    text = parsed.original_question.lower()
    return any(word in text for word in NOW_WORDS)


def trusted_radius_km(parsed: StructuredTravelQuery, default: float = 2.0) -> float:
    """질문에 반경이 명시된 경우에만 GPT의 radius_km 값을 신뢰한다."""
    match = RADIUS_RE.search(parsed.original_question)
    if not match:
        return default
    explicit = float(match.group(1))
    return explicit


def trusted_time_window(parsed: StructuredTravelQuery) -> str | None:
    """원문에 시간 표현이 있을 때만 생성된 time_window를 사용한다."""
    text = parsed.original_question.lower()
    if (
        any(word in text for word in TIME_WORDS)
        or re.search(r"\d{1,2}\s*시", text)
        or re.search(r"\b\d{1,2}:\d{2}\b", text)
    ):
        return parsed.filters.time_window
    return None


def trusted_visit_date(parsed: StructuredTravelQuery, today: date | None = None) -> date | None:
    """상위 파서의 날짜 누락·요일 오해를 원문의 명시적 표현으로 교정한다."""
    base = today or date.today()
    text = parsed.original_question.lower()
    if "모레" in text or "day after tomorrow" in text:
        return base + timedelta(days=2)
    if "내일" in text or "tomorrow" in text:
        return base + timedelta(days=1)
    if "오늘" in text or "today" in text:
        return base
    for label, weekday in WEEKDAY_INDEX.items():
        if label not in text:
            continue
        delta = (weekday - base.weekday()) % 7
        if ("다음" in text or "next" in text) and delta == 0:
            delta = 7
        return base + timedelta(days=delta)
    iso_match = re.search(r"\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\b", text)
    if iso_match:
        return date(*(int(part) for part in iso_match.groups()))
    korean_match = re.search(r"(?:(20\d{2})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    if korean_match:
        year, month, day = korean_match.groups()
        return date(int(year or base.year), int(month), int(day))
    return parsed.filters.start_date


def target_visit_datetime(parsed: StructuredTravelQuery) -> datetime | None:
    """명시된 방문 날짜와 시간대를 실제 영업시간 판정 시각으로 바꾼다."""
    visit_date = trusted_visit_date(parsed)
    window = trusted_time_window(parsed)
    if visit_date is None or not window:
        return None
    lowered = str(window).strip().lower()
    hour = TIME_WINDOW_HOURS.get(lowered)
    minute = 0
    if hour is None:
        # GPT가 time_window에 ISO 시각 또는 ISO 범위를 넣는 경우 첫 방문 시각을 쓴다.
        match = re.search(r"t(\d{1,2}):(\d{2})", lowered)
        if not match:
            match = re.search(r"\b(\d{1,2}):(\d{2})\b", lowered)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
        else:
            match = re.search(r"\b(\d{1,2})\s*(am|pm)\b", lowered)
            if match:
                hour = int(match.group(1)) % 12 + (12 if match.group(2) == "pm" else 0)
            else:
                match = re.search(r"(?:(오전|오후)\s*)?(\d{1,2})\s*시", lowered)
                if match:
                    hour = int(match.group(2)) % 24
                    if match.group(1) == "오후" and hour < 12:
                        hour += 12
    if hour is None or not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return datetime.combine(visit_date, time(hour, minute))


def trusted_budget_bounds(parsed: StructuredTravelQuery) -> tuple[int | None, int | None]:
    """원문에 실제 금액 표현이 있을 때만 GPT가 만든 예산 필터를 신뢰한다."""
    text = parsed.original_question.lower()
    if not re.search(r"(?:\d[\d,]*(?:\.\d+)?\s*(?:만\s*)?원|₩|\bwon\b|\bbudget\b)", text):
        return None, None
    return parsed.filters.budget_min_krw, parsed.filters.budget_max_krw


def extract_min_rating(parsed: StructuredTravelQuery) -> float | None:
    match = RATING_RE.search(parsed.original_question)
    return float(match.group(1)) if match else None


def prefers_high_rating(parsed: StructuredTravelQuery) -> bool:
    return bool(HIGH_RATING_PREFERENCE_RE.search(parsed.original_question))


def structured_feature_fields(features: list[str]) -> tuple[str, ...]:
    text = " ".join(features)
    return tuple(
        field
        for field, patterns in FEATURE_PATTERNS.items()
        if _feature_matches(text, patterns)
    )


def explicit_feature_fields(parsed: StructuredTravelQuery) -> tuple[str, ...]:
    """GPT가 filter 대신 theme/notes에 둔 명시적 시설 조건을 원문에서 복구한다."""
    text = parsed.original_question.lower()
    sentences = re.split(r"[.!?。,]|\n", text)
    required: list[str] = []
    for field, patterns in FEATURE_PATTERNS.items():
        if not _feature_matches(text, patterns):
            continue
        context = " ".join(
            sentence for sentence in sentences if _feature_matches(sentence, patterns)
        )
        if any(pattern in context for pattern in OPTIONAL_FEATURE_PATTERNS):
            continue
        if any(pattern in context for pattern in NEGATIVE_FEATURE_PATTERNS):
            continue
        required.append(field)
    return tuple(required)


def effective_query_language(parsed: StructuredTravelQuery) -> str:
    """명백한 영문 질문을 GPT가 ko로 잘못 표기한 경우 검색 테이블 언어를 교정한다."""
    return detect_input_language(
        parsed.original_question,
        fallback=parsed.language,
    )


def _is_filter_only_fragment(text: str) -> bool:
    return bool(RATING_RE.search(text) or CURRENCY_RE.search(text))


# str.strip()은 '문자 집합'을 지우므로 strip(" ,|이고이며")는 '떡볶이' -> '떡볶',
# '곱창구이' -> '곱창구' 처럼 어미가 아닌 글자까지 잘라낸다. 반드시 토큰 단위로 지운다.
DANGLING_CONJUNCTION_RE = re.compile(
    r"^[\s,|]*(?:이고|이며|이면서|그리고|and)\b[\s,|]*"
    r"|[\s,|]*(?:이고|이며|이면서|그리고|and)[\s,|]*$",
    re.IGNORECASE,
)


def _strip_dangling_conjunctions(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = DANGLING_CONJUNCTION_RE.sub(" ", text).strip(" ,|")
    return text


def _clean_base_query(text: str) -> str:
    text = RATING_RE.sub(" ", text)
    text = re.sub(
        rf"(?:예산|가격|메뉴\s*가격|1인\s*메뉴\s*가격)?\s*{CURRENCY_RE.pattern}"
        rf"(?:\s*(?:이하|이상|미만|초과|사이|정도|까지|부터|or less|or more))?",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    return _strip_dangling_conjunctions(re.sub(r"\s+", " ", text).strip())


def build_semantic_query(
    task: StructuredQueryTask,
    filters: StructuredSearchFilters,
) -> str:
    """위치·포맷 라벨을 제외하고 Task 의미와 누락된 theme만 임베딩 문장에 남긴다."""
    query = task.search_query.strip()
    if filters.location:
        query = re.sub(re.escape(filters.location), " ", query, flags=re.IGNORECASE)
    query = _clean_base_query(query)
    query = re.sub(r"^\s*(?:이고|이며|이면서|and)\s*", "", query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()

    parts = [query]
    lowered = query.lower()
    for theme in task.themes:
        clean = theme.strip()
        if clean and not _is_filter_only_fragment(clean) and clean.lower() not in lowered:
            parts.append(clean)
    if task.notes and not _is_filter_only_fragment(task.notes):
        parts.append(task.notes.strip())
    return " ".join(part for part in parts if part).strip() or task.search_query.strip()


def build_menu_query(
    task: StructuredQueryTask,
    filters: StructuredSearchFilters,
) -> str:
    """메뉴 검색은 분위기 theme/notes를 덧붙이지 않고 음식·메뉴 중심 Task만 사용한다."""
    query = task.search_query.strip()
    if filters.location:
        query = re.sub(re.escape(filters.location), " ", query, flags=re.IGNORECASE)
    query = _clean_base_query(query)
    return re.sub(r"\s+", " ", query).strip() or task.search_query.strip()


@dataclass(frozen=True)
class StructuredRestaurantSearchPlan:
    task_id: str
    retrieval_query: str
    review_query: str
    menu_query: str
    required_menu_terms: tuple[str, ...]
    requested_category: str | None
    location_name: str | None
    origin_lat: float | None
    origin_lng: float | None
    radius_km: float
    open_now: bool
    include_weather_features: bool
    min_rating: float | None
    prefer_high_rating: bool
    required_feature_fields: tuple[str, ...]
    excluded_feature_fields: tuple[str, ...]
    target_time_window: str | None
    target_visit_at: datetime | None
    budget_min_krw: int | None
    budget_max_krw: int | None
    top_n: int


__all__ = [
    "ExecutionMode",
    "StructuredRestaurantSearchPlan",
    "build_semantic_query",
    "build_menu_query",
    "effective_task_filters",
    "infer_task_location",
    "derive_source_mode",
    "deduplicate_recommendation_tasks",
    "should_filter_open_now",
    "extract_min_rating",
    "prefers_high_rating",
    "effective_query_language",
    "explicit_feature_fields",
    "structured_feature_fields",
    "trusted_radius_km",
    "trusted_time_window",
    "target_visit_datetime",
    "trusted_visit_date",
    "trusted_budget_bounds",
]
