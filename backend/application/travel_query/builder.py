from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta
from itertools import cycle, islice, permutations
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
from services.location import (
    CITYWIDE_LOCATION_NAME,
    SEOUL_AREA_COORDINATES,
    haversine_km,
    is_citywide_location,
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
        assigned_areas = _select_multi_day_areas(
            collected,
            location,
            int(collected["days"]),
            seed_hint=state.get("reference_at"),
        )
        tasks = _build_multi_day_route_tasks(
            collected,
            location,
            language,
            assigned_areas=assigned_areas,
        )
        route_request = _build_route_request(
            collected,
            location,
            multi_day=True,
            assigned_areas=assigned_areas,
        )

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


def _slot_filters(location: str | None) -> QueryFilters | None:
    """슬롯 고유 지역이 있으면 그 지역을 담은 Task 필터를 만든다."""
    return QueryFilters(location=location) if location else None


def _build_single_tasks(
    collected: dict[str, Any],
    location: str | None,
    language: str,
) -> list[TravelTask]:
    slots = collected.get("requested_slots") or []
    # 방문지별 지역이 다른 멀티지역 요청(예: '강남 파스타랑 홍대 라멘')은
    # 슬롯 단위로 각자 지역을 반영한다.
    if slots and any(slot.get("location") for slot in slots):
        tasks: list[TravelTask] = []
        for index, slot in enumerate(slots, start=1):
            slot_location = slot.get("location") or location
            domain = slot["domain"]
            tasks.append(
                TravelTask(
                    task_id=f"task_{index}",
                    domain=domain,
                    search_query=slot.get("search_query")
                    or _search_query(slot_location, domain, collected, language),
                    themes=slot.get("themes") or collected.get("themes") or [],
                    desired_count=3,
                    filters=_slot_filters(slot_location),
                )
            )
        return tasks

    if not collected.get("requested_domains"):
        raise ValueError("단일 장소 추천에는 검색 도메인이 필요합니다.")
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
    *,
    assigned_areas: list[str] | None = None,
) -> list[TravelTask]:
    start_date = date.fromisoformat(str(collected["start_date"]))
    days = int(collected["days"])
    per_day = {"relaxed": 3, "normal": 5, "packed": 5}[collected["pace"]]
    tasks: list[TravelTask] = []
    for day_index in range(days):
        visit_date = start_date + timedelta(days=day_index)
        slots = _slots_for_multi_day(
            collected,
            per_day,
            day_number=day_index + 1,
            visit_date=visit_date,
        )
        day_area = assigned_areas[day_index] if assigned_areas else None
        if day_area:
            slots = [
                # 다일 루트의 핵심 불변식: 한 Day의 모든 슬롯은 한 권역이다.
                # LLM이 개별 슬롯에 다른 지역을 넣어도 Day 대표 권역이 우선한다.
                {**slot, "location": day_area}
                for slot in slots
            ]
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
    scheduled_slots = _schedule_route_slots(slots)
    for offset, slot in enumerate(scheduled_slots):
        domain: TaskDomain = slot["domain"]
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        themes = slot.get("themes") or collected.get("themes") or []
        slot_location = slot.get("location") or location
        tasks.append(
            TravelTask(
                task_id=f"task_{task_start + offset}",
                domain=domain,
                search_query=slot.get("search_query")
                or _search_query(slot_location, domain, {**collected, "themes": themes}, language),
                themes=themes,
                desired_count=1,
                notes=slot.get("notes"),
                slot_id=f"d{day_number}-{domain}-{domain_counts[domain]}",
                day_number=slot.get("day_number") or day_number,
                visit_date=slot.get("visit_date") or visit_date,
                start_time=slot["start_time"],
                end_date=slot.get("end_date"),
                end_time=slot.get("end_time"),
                filters=_slot_filters(slot.get("location")),
            )
        )
    return tasks


def _build_route_request(
    collected: dict[str, Any],
    location: str | None,
    *,
    multi_day: bool,
    assigned_areas: list[str] | None = None,
) -> dict[str, Any]:
    destination = location
    if not destination and collected.get("preferred_areas"):
        destination = collected["preferred_areas"][0]
    if not destination:
        # 전역 지역이 없는 멀티지역 루트는 첫 슬롯 지역을 대표 목적지로 쓴다.
        for slot in collected.get("requested_slots") or []:
            if slot.get("location"):
                destination = slot["location"]
                break
    preferred_areas = (
        collected.get("preferred_areas")
        or assigned_areas
        or ([destination] if destination else [])
    )
    return {
        "destination": destination,
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
        "preferred_areas": preferred_areas,
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
# 루트/일정은 오전 명소 → 식사 → 카페 → 저녁 식사 순으로 채운다.
# 4·5번째 슬롯에서도 식사와 명소가 자연스럽게 반복되도록 중복을 의도적으로 둔다.
DEFAULT_ROUTE_DOMAINS: list[TaskDomain] = [
    "attraction",
    "restaurant",
    "cafe",
    "attraction",
    "restaurant",
]
DEFAULT_SINGLE_DOMAINS: list[TaskDomain] = ["restaurant"]
ROUTE_INTENTS_FOR_DEFAULT = {"day_trip_route", "multi_day_route"}
ROUTE_SLOT_TIME_TEMPLATES: dict[int, list[str]] = {
    1: ["14:00"],
    2: ["11:00", "18:00"],
    3: ["10:00", "14:00", "18:00"],
    4: ["10:00", "13:00", "16:00", "19:00"],
    5: ["10:00", "12:30", "15:00", "17:00", "19:00"],
}
MULTI_DAY_AREA_PROFILES = {
    # popularity는 여행 수요, coverage는 현재 장소 데이터의 도메인 충실도다.
    # 실제 클릭·저장 통계가 쌓이면 이 두 값을 운영 지표로 교체할 수 있다.
    "종로구": {"popularity": 1.35, "coverage": 1.30},
    "마포구": {"popularity": 1.30, "coverage": 1.20},
    "성동구": {"popularity": 1.25, "coverage": 1.15},
    "강남구": {"popularity": 1.40, "coverage": 1.30},
    "송파구": {"popularity": 1.20, "coverage": 1.15},
    "용산구": {"popularity": 1.15, "coverage": 1.10},
    "중구": {"popularity": 1.10, "coverage": 1.10},
    "서초구": {"popularity": 1.00, "coverage": 1.00},
    "영등포구": {"popularity": 0.95, "coverage": 0.95},
    "광진구": {"popularity": 0.90, "coverage": 0.85},
}


def _area_weight(area: str) -> float:
    profile = MULTI_DAY_AREA_PROFILES[area]
    return profile["popularity"] * 0.6 + profile["coverage"] * 0.4


def _weighted_sample_areas(rng: random.Random, count: int) -> list[str]:
    pool = list(MULTI_DAY_AREA_PROFILES)
    selected: list[str] = []
    for _ in range(min(count, len(pool))):
        weights = [_area_weight(area) for area in pool]
        picked = rng.choices(pool, weights=weights, k=1)[0]
        selected.append(picked)
        pool.remove(picked)
    return selected


def _canonical_multi_day_area(value: object) -> str | None:
    """동네·역 별칭을 하루 권역으로 사용할 자치구 이름에 수렴시킨다."""

    text = str(value or "").strip()
    if text in MULTI_DAY_AREA_PROFILES:
        return text
    coordinates = SEOUL_AREA_COORDINATES.get(text)
    if coordinates is None:
        return None
    latitude, longitude, _ = coordinates
    return min(
        MULTI_DAY_AREA_PROFILES,
        key=lambda area: haversine_km(
            latitude,
            longitude,
            SEOUL_AREA_COORDINATES[area][0],
            SEOUL_AREA_COORDINATES[area][1],
        ),
    )


def _requested_multi_day_areas(collected: dict[str, Any]) -> list[str]:
    raw_areas = [
        *(collected.get("preferred_areas") or []),
        *(
            slot.get("location")
            for slot in (collected.get("requested_slots") or [])
            if slot.get("location")
        ),
    ]
    canonical = [
        area
        for value in raw_areas
        if (area := _canonical_multi_day_area(value)) is not None
    ]
    return list(dict.fromkeys(canonical))


def _area_path_distance(areas: tuple[str, ...]) -> float:
    distance = 0.0
    for current, following in zip(areas, areas[1:]):
        current_lat, current_lng, _ = SEOUL_AREA_COORDINATES[current]
        next_lat, next_lng, _ = SEOUL_AREA_COORDINATES[following]
        distance += haversine_km(current_lat, current_lng, next_lat, next_lng)
    return distance


def _order_areas_by_distance(areas: list[str]) -> list[str]:
    """선택된 권역 집합은 유지하고 Day 간 총 직선거리가 가장 짧게 정렬한다."""

    if len(areas) < 2:
        return areas
    best = min(
        permutations(areas),
        key=lambda route: (_area_path_distance(route), route),
    )
    return list(best)


def _select_multi_day_areas(
    collected: dict[str, Any],
    location: str | None,
    days: int,
    *,
    seed_hint: object = None,
) -> list[str]:
    """서울 전역 일정에 재현 가능한 가중 랜덤 권역을 중복 없이 배정한다."""

    requested_areas = _requested_multi_day_areas(collected)
    if not requested_areas and not is_citywide_location(location):
        return []
    seed_text = "|".join(str(value) for value in (
        collected.get("original_question"),
        collected.get("start_date"),
        collected.get("end_date"),
        seed_hint,
    ))
    seed = int.from_bytes(hashlib.sha256(seed_text.encode("utf-8")).digest()[:8])
    rng = random.Random(seed)
    selected = requested_areas[:days]
    if len(selected) < days:
        remaining_pool = {
            area: profile
            for area, profile in MULTI_DAY_AREA_PROFILES.items()
            if area not in selected
        }
        # 기존 가중치 함수를 유지하면서 명시 권역과 중복되지 않게 뽑는다.
        pool = list(remaining_pool)
        for _ in range(min(days - len(selected), len(pool))):
            picked = rng.choices(
                pool,
                weights=[_area_weight(area) for area in pool],
                k=1,
            )[0]
            selected.append(picked)
            pool.remove(picked)
    return _order_areas_by_distance(selected)


def _domains(collected: dict[str, Any]) -> list[TaskDomain]:
    domains = collected.get("requested_domains") or []
    if domains:
        if collected.get("intent") in ROUTE_INTENTS_FOR_DEFAULT:
            route_domains = [domain for domain in domains if domain != "accommodation"]
            return route_domains or list(DEFAULT_ROUTE_DOMAINS)
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
    explicit_slots = [
        slot
        for slot in _explicit_slots_for_day(
            collected,
            day_number=day_number,
            visit_date=visit_date,
        )
        if slot.get("domain") != "accommodation"
    ]
    selected = explicit_slots[:count]
    remaining = count - len(selected)
    if remaining <= 0:
        return selected

    domains = _domains_for_count(collected, remaining)
    return [*selected, *({"domain": domain} for domain in domains)]


def _explicit_slots_for_day(
    collected: dict[str, Any],
    *,
    day_number: int,
    visit_date: date | str,
) -> list[dict[str, Any]]:
    visit_date_text = str(visit_date)
    return [
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


def _multi_day_activity_domains(
    collected: dict[str, Any],
) -> list[TaskDomain]:
    """명시 도메인을 우선하되 다일 일정의 기본 활동 종류를 없애지 않는다."""

    requested = [
        domain
        for domain in (collected.get("requested_domains") or [])
        if domain != "accommodation"
    ]
    if not requested:
        return list(DEFAULT_ROUTE_DOMAINS)
    return list(dict.fromkeys([*requested, *DEFAULT_ROUTE_DOMAINS]))


def _slots_for_multi_day(
    collected: dict[str, Any],
    count: int,
    *,
    day_number: int,
    visit_date: date | str,
) -> list[dict[str, Any]]:
    """숙소는 별도 추천으로 분리하고 날짜별 활동 슬롯만 구성한다."""

    explicit_slots = [
        slot
        for slot in _explicit_slots_for_day(
            collected,
            day_number=day_number,
            visit_date=visit_date,
        )
        if slot.get("domain") != "accommodation"
    ]

    if len(explicit_slots) > 5:
        raise ValueError("하루 방문 슬롯은 최대 5개까지 지정할 수 있습니다.")
    selected = explicit_slots[:count]
    activity_count = count - len(selected)
    activity_domains = _multi_day_activity_domains(collected)
    activities = [
        {"domain": domain}
        for domain in islice(cycle(activity_domains), max(activity_count, 0))
    ]
    return [*selected, *activities]


def _schedule_route_slots(
    slots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """명시 시각을 보존하고 자동 슬롯에는 시간순 기본 시각을 부여한다."""

    count = len(slots)
    try:
        template = ROUTE_SLOT_TIME_TEMPLATES[count]
    except KeyError as exc:
        raise ValueError("하루 방문 슬롯은 1개 이상 5개 이하여야 합니다.") from exc

    scheduled: list[dict[str, Any]] = []
    for index, raw_slot in enumerate(slots):
        slot = dict(raw_slot)
        if not slot.get("start_time"):
            slot["start_time"] = (
                "22:00"
                if slot.get("domain") == "accommodation"
                else template[index]
            )
        scheduled.append(slot)

    scheduled.sort(key=lambda slot: str(slot["start_time"]))
    start_times = [str(slot["start_time"]) for slot in scheduled]
    if len(start_times) != len(set(start_times)):
        raise ValueError("같은 여행 일차의 슬롯 시작 시각은 중복될 수 없습니다.")
    return scheduled


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
    location = (
        collected.get("location")
        or state.get("current_location_name")
        or ("현재 위치" if collected.get("use_current_location") else None)
    )
    return CITYWIDE_LOCATION_NAME if is_citywide_location(location) else location


def _validation_messages(exc: Exception) -> list[str]:
    if isinstance(exc, ValidationError):
        return [
            f"{'.'.join(str(item) for item in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        ]
    return [str(exc)]
