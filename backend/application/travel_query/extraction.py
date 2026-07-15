import json
from datetime import date, timedelta
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ConfigDict, Field

from application.travel_query.state import TravelQueryGraphState
from schemas.route_planner import HHMMTime, RoutePace
from schemas.structured_query import TaskDomain, TravelIntent


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
상대 날짜는 reference_at을 기준으로 Asia/Seoul 절대 날짜로 변환한다.
기준 시각이 부족해 확정할 수 없을 때만 relative_date_ambiguous=true로 둔다.
단일 추천에서 사용자가 한 곳을 말해도 장소 수 정책은 후속 단계가 처리한다.
당일 루트에서 방문 종류를 명시했다면 explicit_visit_count에 실제 슬롯 수를 넣는다.
당일 루트의 강도 선택은 relaxed=3곳, normal=4곳, packed=5곳으로 매핑한다.
다일 루트의 target_places_per_day는 정확한 전체 검증값으로 만들지 않는다.
날씨를 requested_domains에 넣지 않는다.""",
        ),
        (
            "human",
            """original_question: {original_question}
reference_at: {reference_at}
current_location: {current_location}
previously_collected: {collected}
latest_user_answer: {latest_user_answer}""",
        ),
    ]
)


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
                "latest_user_answer": state.get("latest_user_answer") or "none",
            }
        )
        extraction = (
            result
            if isinstance(result, IntentExtraction)
            else IntentExtraction.model_validate(result)
        )
        extracted = extraction.model_dump(mode="json", exclude_none=True)
        language = extracted.pop("language")
        intent = extracted.pop("intent")
        normalized_question = extracted.pop("normalized_question")
        _apply_deterministic_defaults(intent, extracted)

        collected = dict(state.get("collected", {}))
        collected.update(extracted)
        collected.update(
            {
                "original_question": state["original_question"],
                "language": language,
                "intent": intent,
            }
        )

        return {
            "language": language,
            "intent": intent,
            "normalized_question": normalized_question,
            "collected": collected,
            "latest_user_answer": None,
        }


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
    if requested_slots and not extracted.get("requested_domains"):
        extracted["requested_domains"] = [slot["domain"] for slot in requested_slots]

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
