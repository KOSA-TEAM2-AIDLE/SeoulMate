from collections.abc import Callable
from typing import Any

from application.travel_query.state import TravelQueryGraphState


QuestionFactory = Callable[[dict[str, Any]], str]
ROUTE_MODIFICATION_UNSUPPORTED_MESSAGE = "루트 수정은 지원하지 않습니다."

QUESTION_FACTORIES: dict[str, QuestionFactory] = {
    "intent": lambda _: "어떤 여행 도움을 원하시나요? 장소 추천, 일정, 날씨 중에서 알려주세요.",
    "filters.location": lambda _: "어느 지역을 기준으로 찾아볼까요? 현재 위치를 사용해도 됩니다.",
    "route_request.destination": lambda _: "여행할 지역을 알려주세요.",
    "route_request.period": lambda _: "여행 시작일과 종료일은 언제인가요?",
    "route_request.target_places_per_day": lambda _: (
        "하루에 몇 곳 정도 둘러보고 싶으세요? "
        "여유롭게 3곳, 보통 4곳, 알차게 5곳 중에서 골라주세요."
    ),
    "route_request.pace": lambda _: (
        "일정은 여유롭게, 보통, 알차게 중 어느 정도로 구성할까요?"
    ),
    "weather_request.location_name": lambda _: "어느 지역의 날씨를 확인할까요?",
    "weather_request.target_date": lambda _: "어느 날짜의 날씨를 확인할까요?",
    "filters.budget_scope": lambda _: (
        "말씀하신 예산은 1인 기준인가요, 전체 인원 기준인가요?"
    ),
    "filters.budget_range": lambda _: (
        "최소 예산과 최대 예산의 범위를 다시 알려주세요."
    ),
    "date_confirmation": lambda _: "말씀하신 날짜를 정확한 날짜로 알려주세요.",
}

ENGLISH_QUESTION_FACTORIES: dict[str, QuestionFactory] = {
    "intent": lambda _: (
        "What kind of travel help would you like? "
        "Please choose a place recommendation, itinerary, or weather information."
    ),
    "filters.location": lambda _: (
        "Which area should I search around? You can also use your current location."
    ),
    "route_request.destination": lambda _: "Which area would you like to visit?",
    "route_request.period": lambda _: (
        "What are the start and end dates of your trip?"
    ),
    "route_request.target_places_per_day": lambda _: (
        "How many places would you like to visit per day? "
        "Please choose relaxed (3), normal (4), or packed (5)."
    ),
    "route_request.pace": lambda _: (
        "Would you like a relaxed, normal, or packed itinerary?"
    ),
    "weather_request.location_name": lambda _: (
        "Which area's weather would you like to check?"
    ),
    "weather_request.target_date": lambda _: (
        "Which date's weather would you like to check?"
    ),
    "filters.budget_scope": lambda _: (
        "Is that budget per person or for the entire group?"
    ),
    "filters.budget_range": lambda _: (
        "Please provide the minimum and maximum budget again."
    ),
    "date_confirmation": lambda _: (
        "Please provide the date you mentioned as an exact calendar date."
    ),
}

MISSING_FIELD_PRIORITY = [
    "intent",
    "route_request.destination",
    "filters.location",
    "route_request.period",
    "weather_request.location_name",
    "weather_request.target_date",
    "date_confirmation",
    "route_request.target_places_per_day",
    "route_request.pace",
    "filters.budget_scope",
]


def questions_for_missing_fields(
    missing_fields: list[str],
    collected: dict[str, Any],
    language: str = "ko",
) -> str:
    factories = (
        ENGLISH_QUESTION_FACTORIES
        if str(language).lower().startswith("en")
        else QUESTION_FACTORIES
    )
    questions = [
        factories[field](collected)
        for field in missing_fields[:2]
    ]
    return " ".join(questions)


def _has_location(
    state: TravelQueryGraphState,
    collected: dict[str, Any],
) -> bool:
    if collected.get("location"):
        return True
    return bool(
        collected.get("use_current_location")
        and state.get("current_latitude") is not None
        and state.get("current_longitude") is not None
    )


def _route_period_is_complete(collected: dict[str, Any]) -> bool:
    return bool(
        collected.get("start_date")
        and collected.get("end_date")
        and collected.get("days") is not None
        and collected.get("nights") is not None
    )


def find_missing_fields(state: TravelQueryGraphState) -> list[str]:
    collected = state.get("collected", {})
    intent = state.get("intent")
    missing: set[str] = set()

    if intent is None:
        missing.add("intent")
        return ["intent"]

    has_location = _has_location(state, collected)
    if intent == "single_place_recommendation" and not has_location:
        missing.add("filters.location")

    if intent == "day_trip_route":
        if not has_location:
            missing.add("route_request.destination")
        if not _route_period_is_complete(collected):
            missing.add("route_request.period")
        explicit_count = collected.get("explicit_visit_count")
        target = collected.get("target_places_per_day")
        if target is None and explicit_count is None:
            missing.add("route_request.target_places_per_day")

    if intent == "multi_day_route":
        if not has_location:
            missing.add("route_request.destination")
        if not _route_period_is_complete(collected):
            missing.add("route_request.period")
        if collected.get("pace") is None:
            missing.add("route_request.pace")

    if intent == "weather_information":
        if not has_location:
            missing.add("weather_request.location_name")
        if collected.get("start_date") is None:
            missing.add("weather_request.target_date")

    if collected.get("relative_date_ambiguous"):
        missing.add("date_confirmation")
    if collected.get("budget_ambiguous") and not collected.get("budget_scope"):
        missing.add("filters.budget_scope")

    return [field for field in MISSING_FIELD_PRIORITY if field in missing]


def check_required_information(
    state: TravelQueryGraphState,
) -> TravelQueryGraphState:
    if state.get("intent") == "modify_route":
        return {
            "status": "unsupported",
            "missing_fields": [],
            "assistant_message": ROUTE_MODIFICATION_UNSUPPORTED_MESSAGE,
            "structured_query": None,
        }

    missing_fields = find_missing_fields(state)
    if not missing_fields:
        return {
            "status": "building",
            "missing_fields": [],
            "assistant_message": None,
        }

    collected = state.get("collected", {})
    return {
        "status": "collecting",
        "missing_fields": missing_fields,
        "assistant_message": questions_for_missing_fields(
            missing_fields,
            collected,
            state.get("language", collected.get("language", "ko")),
        ),
    }
