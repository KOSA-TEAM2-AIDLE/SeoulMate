"""여행 질문의 인텐트와 구조화 조건을 추출하는 모델."""

import json
import re
from datetime import date, timedelta
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ConfigDict, Field

from application.travel_query.state import TravelQueryGraphState
from core.language import detect_input_language
from schemas.route_planner import HHMMTime, RoutePace
from schemas.structured_query import TaskDomain, TravelIntent
from services.location import (
    CITYWIDE_LOCATION_NAME,
    is_citywide_location,
    wants_citywide_search,
)


class RequestedVisitSlot(BaseModel):
    """A visit purpose explicitly stated by the user, not a recommended place."""

    model_config = ConfigDict(extra="forbid")

    domain: TaskDomain
    search_query: str | None = None
    themes: list[str] | None = None
    notes: str | None = None
    day_number: int | None = Field(default=None, ge=1)
    visit_date: date | None = None
    start_time: HHMMTime | None = None
    end_date: date | None = None
    end_time: HHMMTime | None = None


class IntentExtraction(BaseModel):
    """사용자 원문과 추가 답변에서 명시적으로 확인된 조건."""

    model_config = ConfigDict(extra="forbid")

    language: Literal["ko", "en"]
    intent: TravelIntent
    normalized_question: str = Field(min_length=1)
    location: str | None = None
    use_current_location: bool | None = None
    radius_km: float | None = Field(default=None, gt=0)
    start_date: date | None = None
    end_date: date | None = None
    nights: int | None = Field(default=None, ge=0)
    days: int | None = Field(default=None, ge=1)
    explicit_visit_count: int | None = Field(default=None, ge=1, le=35)
    target_places_per_day: int | None = Field(default=None, ge=1, le=5)
    pace: RoutePace | None = None
    requested_domains: list[TaskDomain] | None = None
    requested_slots: list[RequestedVisitSlot] | None = None
    themes: list[str] | None = None
    party_size: int | None = Field(default=None, ge=1)
    adults: int | None = Field(default=None, ge=1)
    children: int | None = Field(default=None, ge=0)
    transportation: list[str] | None = None
    accessibility: list[str] | None = None
    required_features: list[str] | None = None
    excluded_features: list[str] | None = None
    arrival_at: HHMMTime | None = None
    arrival_location: str | None = None
    departure_at: HHMMTime | None = None
    departure_location: str | None = None
    preferred_areas: list[str] | None = None
    must_visit: list[str] | None = None
    avoid_places: list[str] | None = None
    target_time: HHMMTime | None = None
    budget_min_krw: int | None = Field(default=None, ge=0)
    budget_max_krw: int | None = Field(default=None, ge=0)
    budget_scope: Literal["per_person", "total"] | None = None
    budget_ambiguous: bool = False
    relative_date_ambiguous: bool = False
    target_slot_id: str | None = None
    general_response_instruction: str | None = None


EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """당신은 SeoulMate의 첫 번째 여행 질의 분석기다.
장소를 추천하지 말고 사용자가 명시한 조건만 추출한다.
제공되지 않은 값은 추측하지 말고 null로 둔다.
사용자가 이전 조건을 명시적으로 변경하면 최신 답변을 우선한다.
conversation_history와 previous_structured_query는 이전 추천 문맥이다.
현재 질문에 '그중', '아까', '거기서', '같은 조건', '지역만 바꿔'처럼
이전 요청을 가리키는 표현이 있을 때만 이전 조건 중 변경되지 않은 값을 상속한다.
현재 질문이 독립적인 새 요청이면 이전 조건을 상속하지 않는다.
후속 질문에서는 normalized_question을 이전 조건과 현재 변경사항을 합친 독립적인 요청으로 만든다.
상대 날짜는 reference_at을 기준으로 Asia/Seoul 절대 날짜로 변환한다.
기준 시각이 부족해 확정할 수 없을 때만 relative_date_ambiguous=true로 둔다.
단일 추천에서 사용자가 한 곳을 말해도 장소 수 정책은 후속 단계가 처리한다.
당일 루트에서 방문 종류를 명시했다면 explicit_visit_count에 실제 슬롯 수를 넣는다.
당일 루트의 강도 선택은 relaxed=3곳, normal=4곳, packed=5곳으로 매핑한다.
다일 루트의 target_places_per_day는 정확한 전체 검증값으로 만들지 않는다.
날씨를 requested_domains에 넣지 않는다.
도메인 기준은 다음과 같다.
- restaurant: 식당, 음식점, 맛집, 식사, 음식 종류나 메뉴
- cafe: 카페, 커피, 디저트, 베이커리, 찻집
- accommodation: 숙소, 호텔, 모텔, 게스트하우스, 호스텔, 숙박
- attraction: 관광지, 명소, 문화시설, 전시, 미술관, 박물관, 공원, 역사 유적, 쇼핑 관광, 체험, 축제, 행사, 공연
복합 질문에는 명시된 모든 requested_domains 또는 requested_slots를 만든다.
'경복궁 근처/주변/에서 가까운'은 location='경복궁'으로 추출한다.
'내 근처/내 주변/현재 위치에서'는 use_current_location=true로 추출한다.""",
        ),
        (
            "human",
            """original_question: {original_question}
reference_at: {reference_at}
current_location: {current_location}
previously_collected: {collected}
missing_fields: {missing_fields}
conversation_history: {conversation_history}
previous_structured_query: {previous_structured_query}
latest_user_answer: {latest_user_answer}

normalized_question은 최초 질문과 확정된 추가 답변을 모두 포함한 독립적인 요청이어야 한다.
다음 모델에는 대화 기록 없이 normalized_question만 전달될 수 있다.""",
        ),
    ]
)


CLARIFICATION_FIELD_KEYS: dict[str, set[str]] = {
    "filters.location": {"location", "use_current_location", "radius_km"},
    "route_request.destination": {
        "location",
        "use_current_location",
        "preferred_areas",
    },
    "route_request.period": {
        "start_date",
        "end_date",
        "nights",
        "days",
        "relative_date_ambiguous",
        "arrival_at",
        "departure_at",
    },
    "route_request.target_places_per_day": {
        "target_places_per_day",
        "explicit_visit_count",
        "pace",
    },
    "route_request.pace": {"pace", "target_places_per_day"},
    "weather_request.location_name": {"location", "use_current_location"},
    "weather_request.target_date": {
        "start_date",
        "target_time",
        "relative_date_ambiguous",
    },
    "filters.budget_scope": {"budget_scope", "budget_ambiguous"},
    "filters.budget_range": {
        "budget_min_krw",
        "budget_max_krw",
        "budget_ambiguous",
    },
    "date_confirmation": {
        "start_date",
        "end_date",
        "nights",
        "days",
        "relative_date_ambiguous",
    },
}

# 추가 답변에는 요청한 누락값 외에도 "3곳, 분위기 좋은"처럼 유용한 선호 조건이
# 함께 포함될 수 있으므로 아래 필드는 추가로 병합한다.
ADDITIVE_CLARIFICATION_KEYS = {
    "themes",
    "requested_domains",
    "requested_slots",
    "transportation",
    "accessibility",
    "required_features",
    "excluded_features",
    "preferred_areas",
    "must_visit",
    "avoid_places",
    "party_size",
    "adults",
    "children",
}

# 각 AGENTS 에서 Domain 분류를 위한 세부적인 키워드가 있다면 이곳에 추가하면 됩니다.
# 시설을 제외한 나머지는 임의로 추가해두었습니다.
DOMAIN_TERMS: dict[TaskDomain, tuple[str, ...]] = {
    "restaurant": ("음식점", "맛집", "식당", "한식", "중식", "일식", "양식", "식사", "메뉴"),
    "cafe": ("베이커리", "디저트", "카페", "커피", "찻집"),
    "accommodation": ("게스트하우스", "호스텔", "리조트", "숙박", "숙소", "호텔", "모텔"),
    "attraction": (
        "문화시설", "문화 명소", "전시회", "미술관", "박물관", "관광지",
        "역사 유적", "쇼핑 관광", "전시", "축제", "행사", "공연", "명소", "공원", "체험",
    ),
    "etc": (),
}

CURRENT_LOCATION_TERMS = ("내 근처", "내 주변", "현재 위치에서", "여기 근처", "여기 주변")
LOCATION_RELATION_PATTERN = re.compile(
    r"([0-9A-Za-z가-힣·]+(?:\s+[0-9A-Za-z가-힣·]+){0,2})\s*"
    r"(?:근처|주변|인근|에서\s*가까운|이랑\s*가까운)"
)


def _apply_high_confidence_fallback(question: str, extracted: dict[str, Any]) -> None:
    """명확한 표현만 보정하며 모델이 확정한 값은 덮어쓰지 않는다."""
    normalized = re.sub(r"\s+", " ", question).strip().casefold()
    if "use_current_location" not in extracted and any(term in normalized for term in CURRENT_LOCATION_TERMS):
        extracted["use_current_location"] = True

    if not extracted.get("location") and not extracted.get("use_current_location"):
        match = LOCATION_RELATION_PATTERN.search(normalized)
        if match:
            extracted["location"] = match.group(1).strip()

    if not extracted.get("requested_domains"):
        matches: list[tuple[int, TaskDomain]] = []
        for domain, terms in DOMAIN_TERMS.items():
            positions = [(normalized.find(term), term) for term in terms if term in normalized]
            if not positions:
                continue
            position, _ = min(positions)
            matches.append((position, domain))
        extracted["requested_domains"] = [
            domain for _, domain in sorted(matches, key=lambda item: item[0])
        ]

    if "attraction" in (extracted.get("requested_domains") or []) and not extracted.get("themes"):
        attraction_terms = [
            term for term in DOMAIN_TERMS["attraction"] if term in normalized
        ]
        if attraction_terms:
            extracted["themes"] = attraction_terms


def create_intent_extraction_chain(
    model: BaseChatModel,
) -> Runnable[dict[str, Any], IntentExtraction]:
    structured_model = model.with_structured_output(IntentExtraction)
    return EXTRACTION_PROMPT | structured_model


class TravelIntentExtractor:
    def __init__(
        self,
        chain: Runnable[dict[str, Any], IntentExtraction | dict[str, Any]],
    ) -> None:
        self._chain = chain

    async def __call__(
        self,
        state: TravelQueryGraphState,
    ) -> TravelQueryGraphState:
        latest_answer = state.get("latest_user_answer")
        missing_fields = state.get("missing_fields", [])
        result = await self._chain.ainvoke(
            {
                "original_question": state["original_question"],
                "reference_at": state.get("reference_at") or "unknown",
                "current_location": state.get("current_location_name") or "unknown",
                "collected": json.dumps(
                    state.get("collected", {}),
                    ensure_ascii=False,
                    default=str,
                ),
                "missing_fields": json.dumps(missing_fields, ensure_ascii=False),
                "conversation_history": json.dumps(
                    state.get("conversation_history", []),
                    ensure_ascii=False,
                    default=str,
                ),
                "previous_structured_query": json.dumps(
                    state.get("previous_structured_query"),
                    ensure_ascii=False,
                    default=str,
                ),
                "latest_user_answer": latest_answer or "none",
            }
        )
        extraction = (
            result
            if isinstance(result, IntentExtraction)
            else IntentExtraction.model_validate(result)
        )
        extracted = extraction.model_dump(mode="json", exclude_none=True)
        model_language = extracted.pop("language")
        language = detect_input_language(
            state["original_question"],
            fallback=state.get("language") or model_language,
        )
        extracted_intent = extracted.pop("intent")
        llm_normalized_question = extracted.pop("normalized_question")
        budget_source = (
            latest_answer
            if isinstance(latest_answer, str) and missing_fields
            else state["original_question"]
        )
        if (
            extracted.get("budget_ambiguous")
            and extracted.get("budget_min_krw") is None
            and extracted.get("budget_max_krw") is None
            and not re.search(
                r"(?:예산|가격|금액|비용|원\b|만원|천원|krw|budget|price|cost|won|₩)",
                budget_source,
                flags=re.IGNORECASE,
            )
        ):
            # '총 3곳' 같은 방문 수를 금액으로 오인한 결과는 HITL로 보내지 않는다.
            extracted["budget_ambiguous"] = False
        extracted_location = extracted.get("location")
        location_clarification = bool(
            latest_answer is not None
            and any(
                field in {"filters.location", "route_request.destination"}
                for field in missing_fields
            )
        )
        location_source = (
            latest_answer if isinstance(latest_answer, str) else state["original_question"]
        )
        if is_citywide_location(extracted_location) or (
            not extracted_location
            and wants_citywide_search(
                location_source,
                location_clarification=location_clarification,
            )
        ):
            extracted["location"] = CITYWIDE_LOCATION_NAME
        intent = (
            state["intent"]
            if latest_answer is not None
            and missing_fields
            and state.get("intent") is not None
            else extracted_intent
        )
        _apply_deterministic_defaults(intent, extracted)
        _apply_current_location_hint(state, extracted)

        collected = dict(state.get("collected", {}))
        if latest_answer is not None and missing_fields:
            collected.update(_clarification_patch(extracted, missing_fields))
        else:
            collected.update(extracted)
        collected.update(
            {
                "original_question": state["original_question"],
                "language": language,
                "intent": intent,
            }
        )
        normalized_question = _resolved_question(
            state,
            collected,
            llm_normalized_question,
        )

        return {
            "language": language,
            "intent": intent,
            "normalized_question": normalized_question,
            "collected": collected,
            "latest_user_answer": None,
        }


CURRENT_LOCATION_HINT_RE = re.compile(
    r"(?:여기|이곳|현재\s*위치|내\s*위치|내\s*(?:주변|근처)|"
    r"around\s+here|near\s+me|my\s+location|current\s+location)",
    re.IGNORECASE,
)


def _apply_current_location_hint(
    state: TravelQueryGraphState,
    extracted: dict[str, Any],
) -> None:
    if extracted.get("location"):
        return
    if (
        state.get("current_latitude") is None
        or state.get("current_longitude") is None
    ):
        return

    text = " ".join(
        str(value)
        for value in (
            state.get("original_question"),
            state.get("latest_user_answer"),
        )
        if value
    )
    if CURRENT_LOCATION_HINT_RE.search(text):
        extracted["use_current_location"] = True


def _clarification_patch(
    extracted: dict[str, Any],
    missing_fields: list[str],
) -> dict[str, Any]:
    allowed = set(ADDITIVE_CLARIFICATION_KEYS)
    for field in missing_fields:
        allowed.update(CLARIFICATION_FIELD_KEYS.get(field, set()))
    return {key: value for key, value in extracted.items() if key in allowed}


def _resolved_question(
    state: TravelQueryGraphState,
    collected: dict[str, Any],
    llm_normalized_question: str,
) -> str:
    if not state.get("conversation_history"):
        return llm_normalized_question

    language = collected.get("language", state.get("language", "ko"))
    details = _confirmed_details(collected, language)
    if not details:
        return llm_normalized_question

    original = state["original_question"].strip()
    if language == "en":
        return f"{original} (confirmed conditions: {', '.join(details)})"
    return f"{original} (추가로 확정된 조건: {', '.join(details)})"


def _confirmed_details(
    collected: dict[str, Any],
    language: str,
) -> list[str]:
    details: list[str] = []
    location = collected.get("location")
    start_date = collected.get("start_date")
    end_date = collected.get("end_date")
    target = collected.get("target_places_per_day")
    pace = collected.get("pace")
    themes = collected.get("themes") or []
    domains = collected.get("requested_domains") or []

    if language == "en":
        if location:
            details.append(f"location {location}")
        if start_date:
            date_text = str(start_date)
            if end_date and end_date != start_date:
                date_text = f"{start_date} to {end_date}"
            details.append(f"date {date_text}")
        if target is not None:
            details.append(f"{target} places per day")
        if pace:
            details.append(f"pace {pace}")
        if themes:
            details.append(f"themes {', '.join(map(str, themes))}")
        if domains:
            details.append(f"visit types {', '.join(map(str, domains))}")
        return details

    if location:
        details.append(f"지역 {location}")
    if start_date:
        date_text = str(start_date)
        if end_date and end_date != start_date:
            date_text = f"{start_date}~{end_date}"
        details.append(f"날짜 {date_text}")
    if target is not None:
        details.append(f"하루 {target}곳")
    if pace:
        pace_label = {
            "relaxed": "여유롭게",
            "normal": "보통",
            "packed": "알차게",
        }.get(str(pace), str(pace))
        details.append(f"일정 강도 {pace_label}")
    if themes:
        details.append(f"테마 {', '.join(map(str, themes))}")
    if domains:
        details.append(f"방문 유형 {', '.join(map(str, domains))}")
    return details


def _apply_deterministic_defaults(
    intent: TravelIntent,
    extracted: dict[str, Any],
) -> None:
    """사용자 결정이 필요 없는 날짜·장소 수 기본값만 채운다."""
    start_date_value = extracted.get("start_date")
    end_date_value = extracted.get("end_date")
    requested_slots = extracted.get("requested_slots") or []
    if requested_slots and extracted.get("explicit_visit_count") is None:
        extracted["explicit_visit_count"] = len(requested_slots)
    if requested_slots:
        extracted["requested_domains"] = list(dict.fromkeys(
            slot["domain"] for slot in requested_slots
        ))

    if intent == "day_trip_route" and start_date_value:
        extracted["end_date"] = start_date_value
        extracted["days"] = 1
        extracted["nights"] = 0
        explicit_count = extracted.get("explicit_visit_count")
        if (
            extracted.get("target_places_per_day") is None
            and explicit_count is not None
        ):
            extracted["target_places_per_day"] = explicit_count
        if explicit_count is not None and extracted.get("pace") is None:
            extracted["pace"] = "normal"
        pace_target = {"relaxed": 3, "normal": 4, "packed": 5}
        pace = extracted.get("pace")
        if (
            explicit_count is None
            and extracted.get("target_places_per_day") is None
            and pace in pace_target
        ):
            extracted["target_places_per_day"] = pace_target[pace]

    if intent != "multi_day_route" or not start_date_value:
        return

    start = date.fromisoformat(start_date_value)
    if end_date_value:
        end = date.fromisoformat(end_date_value)
        days = (end - start).days + 1
        if days > 0:
            extracted["days"] = days
            extracted["nights"] = days - 1
        return

    nights = extracted.get("nights")
    if nights is not None:
        extracted["days"] = nights + 1
        extracted["end_date"] = (start + timedelta(days=nights)).isoformat()
