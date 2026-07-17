from __future__ import annotations

from datetime import date, timedelta
from itertools import cycle, islice
from typing import Any

from pydantic import ValidationError

from application.travel_query.state import TravelQueryGraphState
from schemas.structured_query import (
    QueryFilters,
    StructuredTravelQuery,
    TaskDomain,
    TravelTask,
    WeatherRequest,
)


DOMAIN_LABELS: dict[TaskDomain, dict[str, str]] = {
    "restaurant": {"ko": "식당", "en": "restaurant"},
    "cafe": {"ko": "카페", "en": "cafe"},
    "accommodation": {"ko": "숙소", "en": "accommodation"},
    "attraction": {"ko": "명소", "en": "attraction"},
    "etc": {"ko": "방문 장소", "en": "place to visit"},
}


def build_structured_query(
    state: TravelQueryGraphState,
) -> TravelQueryGraphState:
    """Build and validate the backend contract from confirmed user values."""
    try:
        query = _assemble_query(state)
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return {
            "status": "failed",
            "structured_query": None,
            "validation_errors": _validation_messages(exc),
        }

    return {
        "status": "ready",
        "assistant_message": None,
        "missing_fields": [],
        "collected": {},
        "structured_query": query.model_dump(mode="json"),
        "validation_errors": [],
    }


def _assemble_query(state: TravelQueryGraphState) -> StructuredTravelQuery:
    collected = state.get("collected", {})
    intent = state["intent"]
    language = state.get("language", "ko")
    location = _location_name(state, collected)
    filters = _build_filters(collected, location)

    tasks: list[TravelTask] = []
    route_request: dict[str, Any] | None = None

    if intent == "single_place_recommendation":
        tasks = _build_single_tasks(collected, location, language)
    elif intent == "day_trip_route":
        tasks = _build_day_route_tasks(collected, location, language)
        route_request = _build_route_request(collected, location, multi_day=False)
    elif intent == "multi_day_route":
        tasks = _build_multi_day_route_tasks(collected, location, language)
        route_request = _build_route_request(collected, location, multi_day=True)

    weather_request = _build_weather_request(state, collected, location)
    instruction = None
    if intent == "general_response":
        instruction = collected.get("general_response_instruction") or state.get(
            "normalized_question"
        )

    return StructuredTravelQuery.model_validate(
        {
            "language": language,
            "intent": intent,
            "original_question": state["original_question"],
            "normalized_question": state["normalized_question"],
            "tasks": tasks,
            "filters": filters,
            "source_mode": None,
            "weather_request": weather_request,
            "route_request": route_request,
            "route_context": None,
            "general_response_instruction": instruction,
        }
    )


def _build_filters(
    collected: dict[str, Any],
    location: str | None,
) -> QueryFilters:
    return QueryFilters(
        location=location,
        radius_km=collected.get("radius_km"),
        is_active=True
        if collected.get("intent")
        in {
            "single_place_recommendation",
            "day_trip_route",
            "multi_day_route",
        }
        else None,
        start_date=collected.get("start_date"),
        end_date=collected.get("end_date"),
        party_size=collected.get("party_size"),
        budget_min_krw=collected.get("budget_min_krw"),
        budget_max_krw=collected.get("budget_max_krw"),
        transportation=collected.get("transportation") or [],
        accessibility=collected.get("accessibility") or [],
        required_features=collected.get("required_features") or [],
        excluded_features=collected.get("excluded_features") or [],
    )


def _build_single_tasks(
    collected: dict[str, Any],
    location: str | None,
    language: str,
) -> list[TravelTask]:
    domains = _domains(collected)
    return [
        TravelTask(
            task_id=f"task_{index}",
            domain=domain,
            search_query=_search_query(location, domain, collected, language),
            themes=collected.get("themes") or [],
            desired_count=3,
            filters=None,
        )
        for index, domain in enumerate(domains, start=1)
    ]


def _build_day_route_tasks(
    collected: dict[str, Any],
    location: str | None,
    language: str,
) -> list[TravelTask]:
    target = int(collected["target_places_per_day"])
    visit_date = collected["start_date"]
    slots = _slots_for_day(
        collected,
        target,
        day_number=1,
        visit_date=visit_date,
    )
    return _build_route_tasks_for_day(
        collected,
        location,
        language,
        slots,
        day_number=1,
        visit_date=visit_date,
        task_start=1,
    )


def _build_multi_day_route_tasks(
    collected: dict[str, Any],
    location: str | None,
    language: str,
) -> list[TravelTask]:
    start_date = date.fromisoformat(str(collected["start_date"]))
    days = int(collected["days"])
    per_day = {"relaxed": 3, "normal": 4, "packed": 5}[collected["pace"]]
    tasks: list[TravelTask] = []
    for day_index in range(days):
        visit_date = start_date + timedelta(days=day_index)
        slots = _slots_for_day(
            collected,
            per_day,
            day_number=day_index + 1,
            visit_date=visit_date,
        )
        tasks.extend(
            _build_route_tasks_for_day(
                collected,
                location,
                language,
                slots,
                day_number=day_index + 1,
                visit_date=visit_date,
                task_start=len(tasks) + 1,
            )
        )
    return tasks


def _build_route_tasks_for_day(
    collected: dict[str, Any],
    location: str | None,
    language: str,
    slots: list[dict[str, Any]],
    *,
    day_number: int,
    visit_date: date | str,
    task_start: int,
) -> list[TravelTask]:
    domain_counts: dict[TaskDomain, int] = {}
    tasks: list[TravelTask] = []
    for offset, slot in enumerate(slots):
        domain: TaskDomain = slot["domain"]
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        themes = slot.get("themes") or collected.get("themes") or []
        tasks.append(
            TravelTask(
                task_id=f"task_{task_start + offset}",
                domain=domain,
                search_query=slot.get("search_query")
                or _search_query(location, domain, {**collected, "themes": themes}, language),
                themes=themes,
                desired_count=1,
                notes=slot.get("notes"),
                slot_id=f"d{day_number}-{domain}-{domain_counts[domain]}",
                day_number=slot.get("day_number") or day_number,
                visit_date=slot.get("visit_date") or visit_date,
                start_time=slot.get("start_time"),
                end_date=slot.get("end_date"),
                end_time=slot.get("end_time"),
                filters=None,
            )
        )
    return tasks


def _build_route_request(
    collected: dict[str, Any],
    location: str | None,
    *,
    multi_day: bool,
) -> dict[str, Any]:
    return {
        "destination": location,
        "period": {
            "start_date": collected["start_date"],
            "end_date": collected["end_date"],
            "nights": collected["nights"],
            "days": collected["days"],
        },
        "adults": collected.get("adults", 1),
        "children": collected.get("children", 0),
        "arrival_at": collected.get("arrival_at"),
        "arrival_location": collected.get("arrival_location"),
        "departure_at": collected.get("departure_at"),
        "departure_location": collected.get("departure_location"),
        "pace": collected.get("pace") or "normal",
        "max_places_per_day": 5,
        "target_places_per_day": None
        if multi_day
        else collected["target_places_per_day"],
        "transportation": collected.get("transportation") or [],
        "preferred_areas": collected.get("preferred_areas") or ([location] if location else []),
        "preferred_themes": collected.get("themes") or [],
        "required_features": collected.get("required_features") or [],
        "excluded_features": collected.get("excluded_features") or [],
        "must_visit": collected.get("must_visit") or [],
        "avoid_places": collected.get("avoid_places") or [],
    }


def _build_weather_request(
    state: TravelQueryGraphState,
    collected: dict[str, Any],
    location: str | None,
) -> WeatherRequest | None:
    intent = state["intent"]
    target_date = collected.get("start_date")
    if intent == "weather_information" or (
        target_date is not None
        and intent in {"single_place_recommendation", "day_trip_route", "multi_day_route"}
    ):
        return WeatherRequest(
            query=state["original_question"],
            location_name=location or "현재 위치",
            target_date=target_date,
            target_time=collected.get("target_time"),
            language=state.get("language", "ko"),
        )
    return None


# 장소 종류를 명시하지 않은 요청의 기본 도메인.
# etc로 두면 전부 임시 mock 후보가 되므로 실제 도메인으로 채운다.
# 루트/일정은 "먹고·마시고·볼거리" 조합, 단일 추천은 식당을 기본으로 한다.
DEFAULT_ROUTE_DOMAINS: list[TaskDomain] = ["restaurant", "cafe", "attraction"]
DEFAULT_SINGLE_DOMAINS: list[TaskDomain] = ["restaurant"]
ROUTE_INTENTS_FOR_DEFAULT = {"day_trip_route", "multi_day_route"}


def _domains(collected: dict[str, Any]) -> list[TaskDomain]:
    domains = collected.get("requested_domains") or []
    if domains:
        return domains
    if collected.get("intent") in ROUTE_INTENTS_FOR_DEFAULT:
        return list(DEFAULT_ROUTE_DOMAINS)
    return list(DEFAULT_SINGLE_DOMAINS)


def _domains_for_count(
    collected: dict[str, Any],
    count: int,
) -> list[TaskDomain]:
    domains = _domains(collected)
    return list(islice(cycle(domains), count))


def _slots_for_day(
    collected: dict[str, Any],
    count: int,
    *,
    day_number: int,
    visit_date: date | str,
) -> list[dict[str, Any]]:
    visit_date_text = str(visit_date)
    explicit_slots = [
        slot
        for slot in (collected.get("requested_slots") or [])
        if (
            slot.get("day_number") == day_number
            or (
                slot.get("day_number") is None
                and str(slot.get("visit_date")) == visit_date_text
            )
            or (
                slot.get("day_number") is None
                and slot.get("visit_date") is None
                and day_number == 1
            )
        )
    ]
    selected = explicit_slots[:count]
    remaining = count - len(selected)
    if remaining <= 0:
        return selected

    domains = _domains_for_count(collected, remaining)
    return [*selected, *({"domain": domain} for domain in domains)]


def _search_query(
    location: str | None,
    domain: TaskDomain,
    collected: dict[str, Any],
    language: str,
) -> str:
    parts = [location, *(collected.get("themes") or []), DOMAIN_LABELS[domain][language]]
    return " ".join(str(part).strip() for part in parts if part and str(part).strip())


def _location_name(
    state: TravelQueryGraphState,
    collected: dict[str, Any],
) -> str | None:
    return (
        collected.get("location")
        or state.get("current_location_name")
        or ("현재 위치" if collected.get("use_current_location") else None)
    )


def _validation_messages(exc: Exception) -> list[str]:
    if isinstance(exc, ValidationError):
        return [
            f"{'.'.join(str(item) for item in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        ]
    return [str(exc)]
