"""POST /chat: RAG 30개 → 날씨 재랭킹 → GPT 최종 답변 SSE."""

from __future__ import annotations

import asyncio
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass
import json
import logging
from datetime import date, datetime, time, timedelta
# datetime.time을 time이라는 이름으로 쓰고 있어 time 모듈은 함수만 가져온다.
from time import perf_counter

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.dependencies import domain_registry
from application.recommendation.domain_executor import execute_domain_search
from application.recommendation.group_selection import select_grouped_candidates
from application.recommendation.location_resolution import SearchLocationResolver
from application.recommendation.request_factory import build_domain_search_request
from application.recommendation.route_reason import (
    RouteReasonFacts,
    build_route_reason,
)
from application.recommendation.selection_registry import (
    build_default_selection_registry,
)
from application.travel_query.builder import DOMAIN_LABELS
from application.travel_query.service import TravelQueryService, get_travel_query_service
from application.response.frontend_response_mapper import (
    empty_frontend_response,
    recommendation_frontend_response,
    route_frontend_response,
)
from domains.common.mapper import search_candidate_to_place
from domains.common.models import DomainSearchRequest
from domains.restaurant.mapper import to_legacy_candidate
from application.travel_query.required_info import (
    ROUTE_MODIFICATION_UNSUPPORTED_MESSAGE,
)

from schemas.chat import (
    ChatDone,
    ChatError,
    ChatMetaPlaces,
    ChatMetaRoute,
    ChatRequest,
    ChatToken,
    DayPlan,
    TimeSlot,
)
from schemas.travel_query_api import TravelQueryApiResponse, TravelQueryStartRequest
from schemas.common import Place, ToolResult
from schemas.route_planner import (
    ROUTE_CANDIDATES_PER_SLOT,
    RouteCandidate,
    RoutePlannerInput,
    RouteRequest,
    RouteSlotCandidates,
    TripPeriod,
)
from models.intent.classifier import classify_intent
from services.llm import (
    FINAL_RECOMMENDATION_COUNT,
    GROUP_SELECTION_COUNT,
    LLM_CANDIDATE_COUNT,
    generate_grouped_recommendation_result,
    generate_recommendation_result,
    stream_chat_response,
    stream_mcp_only_answer,
)
from services.location import (
    SEOUL_CENTER,
    geocode_kakao,
    haversine_km,
    is_citywide_location,
)
from services.rag import is_open_at, search_restaurants
from services.query_policy import (
    deduplicate_recommendation_tasks,
    derive_source_mode,
    effective_query_language,
    effective_task_filters,
    trusted_time_window,
    trusted_visit_date,
)
from domains.restaurant.weather_policy import prepare_rag_only_candidates, rerank_with_weather
from domains.attraction.congestion_reranker import AttractionCongestionReranker
from domains.attraction.context_enricher import AttractionContextEnricher
from domains.attraction.weather_reranker import AttractionWeatherReranker
from services.source_router import decide_source_mode, mode_to_intent, normalize_source_mode
from integrations.mcp.congestion_client import CongestionMCPProvider
from integrations.mcp.weather_client import WeatherMCPProvider, get_weather_via_mcp
from application.route.route_planner import generate_route_plan


logger = logging.getLogger(__name__)

# 내부 예외 메시지를 그대로 사용자에게 노출하지 않기 위한 안전한 안내 문구.
GENERIC_ERROR_MESSAGE = {
    "ko": "요청을 처리하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    "en": "Something went wrong while processing your request. Please try again in a moment.",
}


def _safe_error_message(language: str | None) -> str:
    return (
        GENERIC_ERROR_MESSAGE["en"]
        if str(language or "").lower().startswith("en")
        else GENERIC_ERROR_MESSAGE["ko"]
    )


router = APIRouter()
ROUTE_INTENTS = {"route_day", "route_multi"}
PARSED_INTENT_TO_API_INTENT = {
    "multi_day_route": "route_multi",
    "day_trip_route": "route_day",
    "general_response": "chitchat",
}
DOMAIN_DEFAULT_TIMES = {
    "attraction": "14:00",
    "etc": "16:00",
    "restaurant": "19:00",
    "cafe": "20:30",
    "accommodation": "22:00",
}
ATTRACTION_CONGESTION_SOURCE = "Seoul-Congestion-MCP"
ROUTE_RESTAURANT_PREFERRED_DISTANCE_KM = 1.5
ROUTE_RESTAURANT_MAX_DISTANCE_KM = 2.5
ROUTE_RESTAURANT_RANK_PENALTY_KM = 0.25
ROUTE_CAFE_PREFERRED_DISTANCE_KM = 1.5
ROUTE_CAFE_MAX_DISTANCE_KM = 2.5
ROUTE_CAFE_RANK_PENALTY_KM = 0.25
ROUTE_WEATHER_CONCURRENCY = 5
attraction_congestion_reranker = AttractionCongestionReranker(CongestionMCPProvider())
attraction_context_enricher = AttractionContextEnricher(
    congestion_reranker=attraction_congestion_reranker,
    weather_provider=WeatherMCPProvider(),
)
route_attraction_weather_reranker = AttractionWeatherReranker()
domain_selection_registry = build_default_selection_registry()

MEAL_TIME_HINTS = (
    (("아침", "조식", "breakfast"), "09:00"),
    (("브런치", "brunch"), "11:00"),
    (("점심", "런치", "lunch", "noon"), "12:00"),
    (("저녁", "디너", "dinner", "evening"), "19:00"),
    (("야식", "늦은 밤", "late night"), "21:00"),
)


def _route_slot_start_time(task) -> str:
    """첫 GPT가 시각을 비워도 Task의 식사 시간 표현을 일정 순서에 반영한다."""
    if task.start_time:
        return task.start_time
    task_text = " ".join([task.search_query, *task.themes]).lower()
    if task.domain == "restaurant":
        for keywords, start_time in MEAL_TIME_HINTS:
            if any(keyword in task_text for keyword in keywords):
                return start_time
    if task.domain == "cafe":
        return "16:00"
    return DOMAIN_DEFAULT_TIMES.get(task.domain, "16:00")


def _route_slot_start_times(tasks) -> dict[str, str]:
    """앞 식사 시각을 고려해 시각이 없는 카페를 식사 뒤에 배치한다."""
    start_times: dict[str, str] = {}
    previous_restaurant_time: str | None = None
    for task in tasks:
        start_time = _route_slot_start_time(task)
        if task.domain == "cafe" and not task.start_time:
            task_text = " ".join([task.search_query, *task.themes]).lower()
            has_time_hint = any(
                keyword in task_text
                for keywords, _ in MEAL_TIME_HINTS
                for keyword in keywords
            )
            if (
                not has_time_hint
                and previous_restaurant_time is not None
                and previous_restaurant_time >= "18:00"
            ):
                start_time = "20:30"
        if task.domain == "restaurant":
            previous_restaurant_time = start_time
        start_times[task.task_id] = start_time
    return start_times


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _empty_restaurant_message(rag_result: dict, language: str) -> str:
    if rag_result.get("location_resolution_failed"):
        location = rag_result.get("location_name") or "the requested location"
        if str(language).lower().startswith("en"):
            return (
                f"I couldn't identify the location '{location}'. "
                "Try a district, neighborhood, or station name in Seoul."
            )
        return (
            f"'{location}' 지역을 정확히 확인하지 못했습니다. "
            "서울의 구·동·역 이름으로 다시 입력해 주세요."
        )
    if rag_result.get("menu_no_match"):
        terms = ", ".join(rag_result.get("required_menu_terms") or [])
        location = rag_result.get("location_name")
        if str(language).lower().startswith("en"):
            scope = f" near {location}" if location else " in the requested area"
            return (
                f"I couldn't verify a restaurant serving {terms}{scope}. "
                "Try expanding the search radius or changing the location."
            )
        scope = f"{location} 주변" if location else "요청한 지역"
        return (
            f"{scope}에서 {terms} 메뉴가 확인된 식당을 찾지 못했습니다. "
            "검색 반경을 넓히거나 지역을 바꿔 주세요."
        )
    if str(language).lower().startswith("en"):
        return "I couldn't find a restaurant matching all conditions. Try relaxing the search area or filters."
    return "조건에 맞는 식당을 찾지 못했습니다. 검색 범위나 조건을 완화해 주세요."


def _place(
    candidate: dict,
    *,
    rank: int | None = None,
    selection_reason: str | None = None,
    task_id: str | None = None,
) -> Place:
    weather_reasons = candidate.get("weather_reasons", [])
    reason = "; ".join(weather_reasons) if weather_reasons else "식당·리뷰·메뉴 RAG 관련도"
    return Place(
        source_type="restaurant",
        source_id=str(candidate["restaurant_id"]),
        restaurant_id=str(candidate["restaurant_id"]),
        task_id=task_id,
        name=candidate["name"],
        category=candidate.get("category") or "",
        score=float(candidate["score"]),
        reason=selection_reason or reason,
        rank=rank,
        selection_reason=selection_reason,
        address=candidate.get("address"),
        rating=candidate.get("rating"),
        review_count=candidate.get("review_count"),
        image=candidate.get("image"),
        link=candidate.get("link"),
        lat=candidate.get("lat"),
        lng=candidate.get("lng"),
        rag_score=float(candidate.get("rag_score", candidate["score"])),
        weather_score=candidate.get("weather_score"),
        weather_reasons=weather_reasons,
    )


async def _search_structured_task(
    body: ChatRequest,
    task,
    *,
    candidate_count: int,
):
    parsed = body.parsed_query
    if parsed is None:
        raise ValueError("도메인 검색에는 parsed_query가 필요합니다.")
    return await execute_domain_search(
        domain_registry,
        parsed,
        task,
        latitude=body.lat,
        longitude=body.lng,
        current_location_name=body.location_name,
        candidate_count=candidate_count,
        min_rating=body.min_rating,
    )


async def _rerank_attraction_candidates(
    candidates,
    parsed,
    source_mode: str,
    request,
    *,
    include_congestion: bool = True,
):
    # 식당·카페와 같이 검색 모드와 Context 정책을 분리한다.
    # 날씨는 Enricher 내부 조건을 따르고, 관광 혼잡도는 좌표·위치·
    # 명시적 한적함 요청이 있으면 rag_only에서도 보강한다.
    if include_congestion:
        reranked = await attraction_context_enricher.enrich(request, candidates)
    else:
        reranked = await attraction_context_enricher.enrich(
            request,
            candidates,
            include_congestion=False,
        )
    sources = []
    if any(
        candidate.signals.get("congestion_available") is True
        for candidate in reranked
    ):
        sources.append(ATTRACTION_CONGESTION_SOURCE)
    if any(
        candidate.signals.get("weather_available") is True
        for candidate in reranked
    ):
        sources.append("KMA-via-Weather-MCP")
    return reranked, tuple(sources)


async def _structured_weather(body: ChatRequest, source_mode: str):
    if normalize_source_mode(source_mode) not in {"rag_mcp", "mcp_only"}:
        return None, [], []

    parsed = body.parsed_query
    location_name = (
        parsed.filters.location
        or (parsed.weather_request.location_name if parsed.weather_request else None)
        or body.location_name
        or "서울"
        if parsed
        else body.location_name or "서울"
    )
    lat, lng = body.lat, body.lng
    same_as_current = bool(
        parsed
        and location_name
        and body.location_name
        and location_name.strip().lower() == body.location_name.strip().lower()
    )
    # 식당 RAG와 동일하게, 현재 좌표의 지명이 타깃과 같다는 근거가 없으면
    # 날씨도 타깃 위치를 지오코딩한다.
    if parsed and is_citywide_location(location_name):
        lat, lng, location_name = SEOUL_CENTER[0], SEOUL_CENTER[1], "서울"
    elif parsed and location_name and not same_as_current:
        geocoded = await asyncio.to_thread(geocode_kakao, location_name)
        if geocoded:
            lat, lng, location_name = geocoded
        else:
            lat, lng = None, None
    lat = lat if lat is not None else SEOUL_CENTER[0]
    lng = lng if lng is not None else SEOUL_CENTER[1]
    language = effective_query_language(parsed) if parsed else body.lang
    weather_query = (
        parsed.weather_request.query
        if parsed and parsed.weather_request
        else body.message
    )
    weather_target_date = (
        str(parsed.weather_request.target_date)
        if parsed and parsed.weather_request and parsed.weather_request.target_date
        else str(trusted_visit_date(parsed)) if parsed and trusted_visit_date(parsed) else None
    )
    weather_target_time = (
        parsed.weather_request.target_time
        if parsed and parsed.weather_request else None
    ) or (trusted_time_window(parsed) if parsed else None)
    weather = await get_weather_via_mcp(
        weather_query,
        lat,
        lng,
        language,
        location_name,
        target_date=weather_target_date,
        target_time=weather_target_time,
    )
    tool = ToolResult(
        tool_name="get_weather_context",
        params={"lat": lat, "lng": lng, "query": weather_query},
        result={key: value for key, value in weather.items() if key != "error"},
        ok=bool(weather.get("available")),
        source="live" if weather.get("available") else "mock",
        error=weather.get("error"),
    )
    return weather, [tool], ["KMA-via-Weather-MCP"]


async def _execute_structured_tasks(body: ChatRequest, source_mode: str):
    parsed = body.parsed_query
    if parsed is None:
        raise ValueError("structured task 실행에는 parsed_query가 필요합니다.")

    if any(task.domain == "restaurant" for task in parsed.tasks):
        weather, tool_results, weather_sources = await _structured_weather(body, source_mode)
    else:
        weather, tool_results, weather_sources = None, [], []
    places: list[Place] = []
    sources: list[str] = []
    has_mock = False

    for task in parsed.tasks:
        candidate_count = 30 if task.domain == "restaurant" else max(
            min(max(task.desired_count, 1), 3),
            3,
        )
        batch = await _search_structured_task(
            body,
            task,
            candidate_count=candidate_count,
        )
        sources.extend(batch.sources)
        has_mock = has_mock or batch.used_mock
        if task.domain == "restaurant":
            candidates = [to_legacy_candidate(item) for item in batch.candidates]
            if normalize_source_mode(source_mode) == "rag_mcp" and weather is not None:
                candidates = rerank_with_weather(
                    candidates,
                    weather,
                    parsed.original_question,
                    source_mode="rag_mcp",
                )
            else:
                candidates = prepare_rag_only_candidates(candidates)
            count = min(max(task.desired_count, 1), 3)
            places.extend(_place(candidate) for candidate in candidates[:count])
        else:
            attraction_request = build_domain_search_request(
                parsed,
                task,
                latitude=body.lat,
                longitude=body.lng,
                current_location_name=body.location_name,
                candidate_count=candidate_count,
                min_rating=body.min_rating,
            )
            candidates, attraction_sources = await _rerank_attraction_candidates(
                batch.candidates,
                parsed,
                source_mode,
                attraction_request,
            ) if task.domain == "attraction" else (batch.candidates, ())
            sources.extend(attraction_sources)
            count = min(max(task.desired_count, 1), 3)
            places.extend(
                search_candidate_to_place(candidate)
                for candidate in candidates[:count]
            )

    return (
        places,
        tool_results,
        list(dict.fromkeys([*sources, *weather_sources])),
        has_mock,
    )


async def _structured_tasks_stream(body: ChatRequest, source_mode: str, route_intent: str | None = None):
    if route_intent:
        async for event in _structured_route_stream(body, source_mode, route_intent):
            yield event
        return
    places, tool_results, sources, has_mock = await _execute_structured_tasks(body, source_mode)
    parsed = body.parsed_query
    reasons = []
    if has_mock:
        reasons.append("검색기가 없는 도메인은 교체 가능한 임시 고정 후보를 사용했습니다.")
    yield _sse(ChatMetaPlaces(
        intent=mode_to_intent(source_mode),
        places=places,
        tool_results=tool_results,
        reasons=reasons,
        sources=sources,
        result=recommendation_frontend_response(places),
    ).model_dump())

    message = (
        "식당은 실제 검색 결과를 사용했고, 아직 검색기가 없는 도메인은 임시 고정 후보로 구성했습니다."
        if has_mock
        else "구조화된 검색 결과로 후보를 구성했습니다."
    )
    yield _sse(ChatToken(text=message).model_dump())
    yield _sse(ChatDone().model_dump())


def _route_request_from_query(parsed) -> RouteRequest:
    if parsed.route_request is not None:
        return parsed.route_request
    start = parsed.filters.start_date or date.today()
    end = parsed.filters.end_date or start
    days = (end - start).days + 1
    return RouteRequest(
        destination=parsed.filters.location or "서울",
        period=TripPeriod(
            start_date=start,
            end_date=end,
            nights=days - 1,
            days=days,
        ),
        max_places_per_day=min(5, max(1, len(parsed.tasks))),
    )


def _route_accommodation_location(parsed, route_request: RouteRequest) -> str:
    preferred = [
        *route_request.preferred_accommodation_areas,
        *route_request.preferred_areas,
    ]
    if preferred:
        return preferred[0]
    if parsed.filters.location and not is_citywide_location(parsed.filters.location):
        return parsed.filters.location
    return route_request.destination


async def _search_route_accommodation(body, parsed, route_request: RouteRequest):
    """다일 일정 전체에서 공유할 실제 DB 숙소를 한 번만 검색한다."""

    location = _route_accommodation_location(parsed, route_request)
    latitude, longitude = body.lat, body.lng
    if location and not is_citywide_location(location):
        geocoded = await asyncio.to_thread(geocode_kakao, location)
        if geocoded:
            latitude, longitude, _ = geocoded
    lodging_term = "accommodation" if effective_query_language(parsed) == "en" else "숙소"
    search_query = " ".join(
        str(value).strip()
        for value in (location, *route_request.preferred_themes, lodging_term)
        if str(value or "").strip()
    )
    request = DomainSearchRequest(
        task_id="route-accommodation",
        domain="accommodation",
        language=effective_query_language(parsed),
        search_query=search_query,
        themes=route_request.preferred_themes,
        location=location,
        latitude=latitude,
        longitude=longitude,
        current_location_name=body.location_name,
        candidate_count=3,
        # 여행 날짜를 Context에 넣으면 Booking 실시간 스크래퍼가 실행된다.
        context={
            "visit_date": str(route_request.period.start_date),
            "end_date": str(route_request.period.end_date),
        } if route_request.period else {},
    )
    candidates = await domain_registry.get("accommodation").search(request)
    if not candidates:
        return None, []
    places = [
        search_candidate_to_place(candidate, rank=index)
        for index, candidate in enumerate(candidates[:3], start=1)
    ]
    places[0].selection_reason = places[0].reason
    return places[0], places[1:]


def _restaurant_open_at(raw: dict, visit_date: date, slot_time: str) -> bool | None:
    """해당 방문 시각의 영업 여부. 영업시간 정보가 없으면 None을 반환한다."""

    try:
        target = datetime.combine(visit_date, time.fromisoformat(slot_time))
    except ValueError:
        return None
    return is_open_at(raw.get("hours"), target)


def _route_place_reason(
    place: Place,
    facts: dict,
    previous_place: Place | None,
    language: str,
) -> str:
    """도메인과 무관하게 같은 골격의 루트 추천 이유를 만든다."""

    distance_km = None
    if (
        previous_place is not None
        and None not in (place.lat, place.lng, previous_place.lat, previous_place.lng)
    ):
        distance_km = haversine_km(
            previous_place.lat,
            previous_place.lng,
            place.lat,
            place.lng,
        )
    return build_route_reason(
        RouteReasonFacts(
            domain=facts.get("domain") or place.source_type,
            category=place.category,
            rating=place.rating,
            review_count=place.review_count,
            open_at_visit_time=facts.get("open_at_visit_time"),
            visit_time=facts.get("visit_time"),
            weather_condition=facts.get("weather_condition"),
            weather_indoor_evidence=bool(facts.get("weather_indoor_evidence")),
            weather_outdoor_evidence=bool(facts.get("weather_outdoor_evidence")),
            distance_from_previous_km=distance_km,
            is_first_stop=previous_place is None,
        ),
        language,
    )


def _route_area_centroid(days: list[DayPlan]) -> tuple[float, float] | None:
    coordinates = [
        (slot.place.lat, slot.place.lng)
        for day in days
        for slot in day.slots
        if slot.place.lat is not None and slot.place.lng is not None
    ]
    if not coordinates:
        return None
    return (
        sum(latitude for latitude, _ in coordinates) / len(coordinates),
        sum(longitude for _, longitude in coordinates) / len(coordinates),
    )


def _with_accommodation_reason(
    place: Place,
    centroid: tuple[float, float] | None,
    language: str,
) -> Place:
    """숙소는 특정 슬롯이 아니라 일정 전체 권역과의 거리로 설명한다."""

    updated = place.model_copy(deep=True)
    distance_km = (
        haversine_km(centroid[0], centroid[1], place.lat, place.lng)
        if centroid is not None and place.lat is not None and place.lng is not None
        else None
    )
    updated.selection_reason = build_route_reason(
        RouteReasonFacts(
            domain="accommodation",
            category=place.category,
            rating=place.rating,
            review_count=place.review_count,
            distance_from_area_km=distance_km,
        ),
        language,
    )
    updated.reason = updated.selection_reason
    return updated


def _route_candidate_window(candidates, occurrence_index: int):
    """반복 도메인 슬롯이 항상 같은 상위 5곳을 공유하지 않도록 창을 이동한다."""

    start = max(0, occurrence_index)
    return candidates[start:start + ROUTE_CANDIDATES_PER_SLOT]


def _restaurant_route_search_key(prepared) -> tuple:
    """시간만 다른 같은 날의 식당 슬롯은 하나의 넓은 검색으로 묶는다."""

    task, day_number, visit_date, _, _ = prepared
    task_filters = (
        task.filters.model_dump(mode="json", exclude_none=True)
        if task.filters is not None
        else {}
    )
    return (
        day_number,
        str(visit_date),
        task.search_query,
        tuple(task.themes),
        json.dumps(task_filters, ensure_ascii=False, sort_keys=True),
    )


def _task_filters_key(task) -> str:
    task_filters = (
        task.filters.model_dump(mode="json", exclude_none=True)
        if task.filters is not None
        else {}
    )
    return json.dumps(task_filters, ensure_ascii=False, sort_keys=True)


def _route_candidate_occurrence_key(task) -> tuple:
    """같은 검색을 반복하는 슬롯의 후보 창을 순서대로 이동한다.

    날짜를 키에 넣으면 Day마다 창이 0으로 돌아가 같은 검색이 매일 동일한
    상위 후보를 받고, 결국 같은 장소가 여러 날에 배치된다. 후보 요청 수는
    이미 도메인의 전체 슬롯 수를 기준으로 잡으므로 날짜를 넣지 않는다.
    """

    return (
        task.domain,
        task.search_query,
        tuple(task.themes),
        _task_filters_key(task),
    )


def _restaurant_candidate_occurrence_key(task) -> tuple:
    """식당도 점심·저녁뿐 아니라 날짜를 넘어 후보 창을 이어서 이동한다."""

    return (
        task.search_query,
        tuple(task.themes),
        _task_filters_key(task),
    )


def _restaurant_candidates_open_at_slot(candidates, visit_date: date, slot_time: str):
    """해당 슬롯에 확실히 닫힌 식당을 빼고, 영업 확인 후보를 먼저 둔다."""

    try:
        target = datetime.combine(visit_date, time.fromisoformat(slot_time))
    except ValueError:
        return candidates

    open_candidates = []
    unknown_candidates = []
    for candidate in candidates:
        status = is_open_at(candidate.get("hours"), target)
        if status is True:
            open_candidates.append(candidate)
        elif status is None:
            unknown_candidates.append(candidate)
    return [*open_candidates, *unknown_candidates]


def _route_time_minutes(value: str) -> int:
    parsed = time.fromisoformat(value)
    return parsed.hour * 60 + parsed.minute


def _restaurant_anchor_coordinates(
    prepared_tasks,
    batches,
    restaurant_index: int,
    slot_start_times: dict[str, str],
) -> list[tuple[float, float]]:
    """점심·저녁 직전에 방문하는 관광지 후보 좌표를 식당 기준점으로 쓴다."""

    restaurant_task, day_number, _, _, _ = prepared_tasks[restaurant_index]
    restaurant_time = _route_time_minutes(slot_start_times[restaurant_task.task_id])
    attraction_indices = [
        index
        for index, prepared in enumerate(prepared_tasks)
        if prepared[1] == day_number and prepared[0].domain == "attraction"
    ]
    if not attraction_indices:
        return []
    previous = [
        index
        for index in attraction_indices
        if _route_time_minutes(slot_start_times[prepared_tasks[index][0].task_id])
        <= restaurant_time
    ]
    anchor_index = max(
        previous or attraction_indices,
        key=lambda index: _route_time_minutes(
            slot_start_times[prepared_tasks[index][0].task_id]
        ) if previous else -_route_time_minutes(
            slot_start_times[prepared_tasks[index][0].task_id]
        ),
    )
    anchor_occurrence = prepared_tasks[anchor_index][3]
    anchor_candidates = _route_candidate_window(
        batches[anchor_index].candidates,
        anchor_occurrence,
    )
    return [
        (candidate.latitude, candidate.longitude)
        for candidate in anchor_candidates
        if candidate.latitude is not None and candidate.longitude is not None
    ]


def _rank_restaurants_for_route(candidates, anchors):
    """인접 관광지 1.5km 이내를 우선하고 2.5km 밖은 부족할 때만 보충한다."""

    if not anchors:
        return candidates
    ranked = []
    for rank, candidate in enumerate(candidates):
        latitude, longitude = candidate.get("lat"), candidate.get("lng")
        if latitude is None or longitude is None:
            distance = float("inf")
        else:
            distance = min(
                haversine_km(latitude, longitude, anchor_lat, anchor_lng)
                for anchor_lat, anchor_lng in anchors
            )
        distance_tier = (
            0 if distance <= ROUTE_RESTAURANT_PREFERRED_DISTANCE_KM
            else 1 if distance <= ROUTE_RESTAURANT_MAX_DISTANCE_KM
            else 2 if distance < float("inf")
            else 3
        )
        candidate_with_distance = dict(candidate)
        candidate_with_distance["route_anchor_distance_km"] = (
            round(distance, 3) if distance < float("inf") else None
        )
        ranked.append((
            distance_tier,
            distance + rank * ROUTE_RESTAURANT_RANK_PENALTY_KM,
            rank,
            candidate_with_distance,
        ))
    ranked.sort(key=lambda item: item[:3])
    return [item[3] for item in ranked]


def _cafe_neighbor_anchor_coordinates(
    prepared_tasks,
    batches,
    cafe_index: int,
    slot_start_times: dict[str, str],
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """같은 날 카페 직전·직후 관광지 후보 좌표를 각각 반환한다."""

    cafe_task, day_number, _, _, _ = prepared_tasks[cafe_index]
    cafe_time = _route_time_minutes(slot_start_times[cafe_task.task_id])
    attraction_indices = [
        index
        for index, prepared in enumerate(prepared_tasks)
        if prepared[1] == day_number and prepared[0].domain == "attraction"
    ]

    def nearest_indices(*, before: bool) -> list[int]:
        eligible = [
            index
            for index in attraction_indices
            if (
                _route_time_minutes(slot_start_times[prepared_tasks[index][0].task_id])
                < cafe_time
            ) == before
        ]
        if not eligible:
            return []
        target_time = (
            max if before else min
        )(
            _route_time_minutes(slot_start_times[prepared_tasks[index][0].task_id])
            for index in eligible
        )
        return [
            index
            for index in eligible
            if _route_time_minutes(slot_start_times[prepared_tasks[index][0].task_id])
            == target_time
        ]

    def coordinates(indices: list[int]) -> list[tuple[float, float]]:
        result = []
        for index in indices:
            occurrence = prepared_tasks[index][3]
            for candidate in _route_candidate_window(
                batches[index].candidates,
                occurrence,
            ):
                if candidate.latitude is not None and candidate.longitude is not None:
                    result.append((candidate.latitude, candidate.longitude))
        return result

    return (
        coordinates(nearest_indices(before=True)),
        coordinates(nearest_indices(before=False)),
    )


def _rank_cafes_for_route(candidates, previous_anchors, next_anchors):
    """앞뒤 관광지 모두와 가까운 카페를 우선하고 2.5km 밖은 후순위로 둔다."""

    if not previous_anchors and not next_anchors:
        return candidates

    ranked = []
    for rank, candidate in enumerate(candidates):
        if candidate.latitude is None or candidate.longitude is None:
            previous_distance = next_distance = None
            available_distances = []
        else:
            previous_distance = (
                min(
                    haversine_km(
                        candidate.latitude,
                        candidate.longitude,
                        anchor_lat,
                        anchor_lng,
                    )
                    for anchor_lat, anchor_lng in previous_anchors
                )
                if previous_anchors
                else None
            )
            next_distance = (
                min(
                    haversine_km(
                        candidate.latitude,
                        candidate.longitude,
                        anchor_lat,
                        anchor_lng,
                    )
                    for anchor_lat, anchor_lng in next_anchors
                )
                if next_anchors
                else None
            )
            available_distances = [
                distance
                for distance in (previous_distance, next_distance)
                if distance is not None
            ]

        maximum_distance = max(available_distances, default=float("inf"))
        total_distance = sum(available_distances) if available_distances else float("inf")
        distance_tier = (
            0 if maximum_distance <= ROUTE_CAFE_PREFERRED_DISTANCE_KM
            else 1 if maximum_distance <= ROUTE_CAFE_MAX_DISTANCE_KM
            else 2 if maximum_distance < float("inf")
            else 3
        )
        candidate_with_distance = candidate.model_copy(update={
            "signals": {
                **candidate.signals,
                "route_previous_distance_km": (
                    round(previous_distance, 3) if previous_distance is not None else None
                ),
                "route_next_distance_km": (
                    round(next_distance, 3) if next_distance is not None else None
                ),
            },
        })
        ranked.append((
            distance_tier,
            total_distance + rank * ROUTE_CAFE_RANK_PENALTY_KM,
            rank,
            candidate_with_distance,
        ))

    ranked.sort(key=lambda item: item[:3])
    return [item[3] for item in ranked]


def _route_search_concurrency(tasks, max_places_per_day: int) -> int:
    """실제 하루 최대 슬롯 수를 검색 동시 실행 상한으로 사용한다."""

    per_day = Counter(task.day_number or 1 for task in tasks)
    busiest_day = max(per_day.values(), default=1)
    return max(1, min(busiest_day, max_places_per_day, 5))


def _route_weather_time_bucket(slot_time: str) -> str:
    """오전·점심과 오후·저녁 슬롯이 각각 하나의 예보를 공유한다."""

    return "12:00" if _route_time_minutes(slot_time) < 15 * 60 else "18:00"


def _route_task_weather_location(body, parsed, task) -> str:
    return (
        effective_task_filters(parsed, task).location
        or parsed.filters.location
        or body.location_name
        or "서울"
    )


def _route_weather_key(body, parsed, task, visit_date: date, slot_time: str):
    return (
        visit_date.isoformat(),
        _route_weather_time_bucket(slot_time),
        _route_task_weather_location(body, parsed, task),
    )


async def _prefetch_route_weather(
    body,
    parsed,
    prepared_tasks,
    slot_start_times: dict[str, str],
) -> dict[tuple[str, str, str], dict]:
    """루트의 일자·시간대별 예보를 제한된 동시성으로 한 번씩 조회한다."""

    keys = sorted({
        _route_weather_key(
            body,
            parsed,
            task,
            visit_date,
            slot_start_times[task.task_id],
        )
        for task, _, visit_date, _, _ in prepared_tasks
        if task.domain in {"attraction", "restaurant"}
    })
    if not keys:
        return {}

    locations = list(dict.fromkeys(key[2] for key in keys))

    async def resolve_location(location: str):
        same_as_current = bool(
            body.location_name
            and body.lat is not None
            and body.lng is not None
            and location.strip().casefold()
            == body.location_name.strip().casefold()
        )
        if same_as_current:
            return body.lat, body.lng, body.location_name
        geocoded = await asyncio.to_thread(geocode_kakao, location)
        return geocoded or (SEOUL_CENTER[0], SEOUL_CENTER[1], location)

    resolved_values = await asyncio.gather(*(
        resolve_location(location) for location in locations
    ))
    resolved = dict(zip(locations, resolved_values, strict=True))
    semaphore = asyncio.Semaphore(ROUTE_WEATHER_CONCURRENCY)

    async def fetch(key: tuple[str, str, str]):
        target_date, target_time, location = key
        latitude, longitude, resolved_name = resolved[location]
        async with semaphore:
            weather = await get_weather_via_mcp(
                parsed.original_question,
                latitude,
                longitude,
                effective_query_language(parsed),
                resolved_name,
                target_date=target_date,
                target_time=target_time,
            )
        return key, weather

    return dict(await asyncio.gather(*(fetch(key) for key in keys)))


async def _search_route_batches(body, prepared_tasks, concurrency: int):
    semaphore = asyncio.Semaphore(concurrency)

    async def search_one(prepared):
        task = prepared[0]
        required_candidate_count = prepared[4]
        # 공유 검색은 특정 점심/저녁 시각에 종속되지 않는 넓은 후보 풀이어야 한다.
        # 슬롯별 영업시간 판정은 검색 후 _restaurant_candidates_open_at_slot에서 한다.
        search_task = (
            task.model_copy(update={"start_time": None, "end_time": None})
            if task.domain == "restaurant" and hasattr(task, "model_copy")
            else task
        )
        async with semaphore:
            return await _search_structured_task(
                body,
                search_task,
                candidate_count=(
                    max(30, required_candidate_count)
                    if task.domain == "restaurant"
                    else required_candidate_count
                ),
            )

    # 식당은 같은 날·같은 검색 조건이면 점심/저녁 시각만 제외하고 묶는다.
    # 관광지·카페 등 다른 도메인의 실행 방식은 그대로 유지한다.
    grouped: OrderedDict[tuple, list[int]] = OrderedDict()
    representatives: dict[tuple, tuple] = {}
    for index, prepared in enumerate(prepared_tasks):
        task = prepared[0]
        key = (
            ("restaurant", *_restaurant_route_search_key(prepared))
            if task.domain == "restaurant"
            else ("task", index)
        )
        grouped.setdefault(key, []).append(index)
        representatives.setdefault(key, prepared)

    # gather는 완료 시점과 무관하게 그룹의 입력 순서대로 결과를 반환한다.
    group_keys = list(grouped)
    group_batches = await asyncio.gather(
        *(search_one(representatives[key]) for key in group_keys)
    )
    batches = [None] * len(prepared_tasks)
    for key, batch in zip(group_keys, group_batches):
        for index in grouped[key]:
            batches[index] = batch
    return batches


async def _timed(stage: str, awaitable):
    """루트 단계별 소요 시간을 남긴다. 병렬 실행 구간도 각각 측정한다."""

    started = perf_counter()
    try:
        return await awaitable
    finally:
        logger.info("[route-timing] %s %.2fs", stage, perf_counter() - started)


async def _structured_route_stream(body: ChatRequest, source_mode: str, route_intent: str):
    """Task별 5개 후보를 GPT가 대표 1곳과 대안 2곳으로 편성한다."""
    route_started_at = perf_counter()
    parsed = body.parsed_query
    if parsed is None or not parsed.tasks:
        raise ValueError("루트 생성에는 하나 이상의 장소 Task가 필요합니다.")
    route_request = _route_request_from_query(parsed)
    day_count = route_request.period.days
    if (
        route_intent == "route_day"
        and route_request.target_places_per_day is not None
        and len(parsed.tasks) != route_request.target_places_per_day
    ):
        raise ValueError(
            "당일 루트 Task 수가 target_places_per_day와 일치하지 않습니다."
        )
    include_weather = normalize_source_mode(source_mode) == "rag_mcp"
    tool_results: list[ToolResult] = []
    weather_cache: dict[tuple[str, str, str], dict] = {}
    weather_contexts: list[dict] = []

    slot_inputs: list[RouteSlotCandidates] = []
    place_lookup: dict[str, Place] = {}
    # 이유 문장은 루트 확정 뒤에 동선 거리까지 합쳐 한 곳에서 만든다.
    # 여기서는 슬롯 조립 시점에만 알 수 있는 도메인별 사실을 모아둔다.
    reason_facts: dict[str, dict] = {}
    # 후보를 한 곳도 찾지 못해 일정에서 뺀 슬롯의 도메인 목록.
    skipped_slots: list[str] = []
    has_mock = False
    per_day_counts: dict[int, int] = {}
    domain_slot_counts = Counter(task.domain for task in parsed.tasks)
    domain_occurrences: Counter[tuple] = Counter()
    restaurant_occurrences: Counter[tuple] = Counter()
    slot_start_times = _route_slot_start_times(parsed.tasks)
    prepared_tasks = []
    for task in parsed.tasks:
        day_number = task.day_number or 1
        if day_number > day_count:
            raise ValueError(f"{task.task_id}의 day_number가 여행 기간을 벗어났습니다.")
        per_day_counts[day_number] = per_day_counts.get(day_number, 0) + 1
        if per_day_counts[day_number] > route_request.max_places_per_day:
            raise ValueError("하루 방문 슬롯이 max_places_per_day를 초과했습니다.")
        visit_date = task.visit_date or (
            route_request.period.start_date + timedelta(days=day_number - 1)
        )
        expected_date = route_request.period.start_date + timedelta(days=day_number - 1)
        if visit_date != expected_date:
            raise ValueError(f"{task.task_id}의 visit_date와 day_number가 일치하지 않습니다.")
        if task.domain == "restaurant":
            restaurant_key = _restaurant_candidate_occurrence_key(task)
            occurrence_index = restaurant_occurrences[restaurant_key]
            restaurant_occurrences[restaurant_key] += 1
        else:
            occurrence_key = _route_candidate_occurrence_key(task)
            occurrence_index = domain_occurrences[occurrence_key]
            domain_occurrences[occurrence_key] += 1
        required_candidate_count = min(
            100,
            ROUTE_CANDIDATES_PER_SLOT + domain_slot_counts[task.domain] - 1,
        )
        prepared_tasks.append((
            task,
            day_number,
            visit_date,
            occurrence_index,
            required_candidate_count,
        ))

    accommodation_place = None
    accommodation_alternatives = []

    async def safe_accommodation_search():
        try:
            return await _search_route_accommodation(body, parsed, route_request)
        except Exception:
            logger.exception("다일 일정의 분리 숙소 검색 중 예외가 발생했습니다.")
            return None, []

    route_search = _timed("도메인 검색", _search_route_batches(
        body,
        prepared_tasks,
        _route_search_concurrency(parsed.tasks, route_request.max_places_per_day),
    ))
    route_weather = (
        _timed(
            "날씨 프리페치",
            _prefetch_route_weather(body, parsed, prepared_tasks, slot_start_times),
        )
        if include_weather
        else None
    )
    parallel_started_at = perf_counter()
    if day_count > 1:
        if route_weather is not None:
            batches, accommodation_result, weather_cache = await asyncio.gather(
                route_search,
                _timed("숙소 검색", safe_accommodation_search()),
                route_weather,
            )
        else:
            batches, accommodation_result = await asyncio.gather(
                route_search,
                _timed("숙소 검색", safe_accommodation_search()),
            )
        accommodation_place, accommodation_alternatives = accommodation_result
    else:
        if route_weather is not None:
            batches, weather_cache = await asyncio.gather(
                route_search,
                route_weather,
            )
        else:
            batches = await route_search

    logger.info(
        "[route-timing] 병렬 구간 합계 %.2fs",
        perf_counter() - parallel_started_at,
    )
    assembly_started_at = perf_counter()

    for (target_date, target_time, location), weather in weather_cache.items():
        weather_contexts.append({
            **weather,
            "date": target_date,
            "time": target_time,
            "location": location,
        })
        tool_results.append(ToolResult(
            tool_name="get_weather_context",
            params={
                "location": location,
                "target_date": target_date,
                "target_time": target_time,
            },
            result={key: value for key, value in weather.items() if key != "error"},
            ok=bool(weather.get("available")),
            source="live" if weather.get("available") else "mock",
            error=weather.get("error"),
        ))

    for prepared_index, (prepared, batch) in enumerate(zip(prepared_tasks, batches)):
        (
            task,
            day_number,
            visit_date,
            occurrence_index,
            required_candidate_count,
        ) = prepared
        candidates: list[RouteCandidate] = []
        has_mock = has_mock or batch.used_mock
        if task.domain == "restaurant":
            slot_time = slot_start_times[task.task_id]
            weather = weather_cache.get(
                _route_weather_key(body, parsed, task, visit_date, slot_time)
            )
            ranked = [to_legacy_candidate(item) for item in batch.candidates]
            ranked = (
                rerank_with_weather(ranked, weather, parsed.original_question, source_mode="rag_mcp")
                if include_weather and weather is not None
                else prepare_rag_only_candidates(ranked)
            )
            ranked = _restaurant_candidates_open_at_slot(
                ranked,
                visit_date,
                slot_time,
            )
            anchors = _restaurant_anchor_coordinates(
                prepared_tasks,
                batches,
                prepared_index,
                slot_start_times,
            )
            ranked = _rank_restaurants_for_route(ranked, anchors)
            for raw in ranked[:ROUTE_CANDIDATES_PER_SLOT]:
                # candidate_id는 플래너가 한 슬롯의 후보를 고르는 실행용 ID다.
                # 같은 식당이 점심/저녁 양쪽 후보에 포함될 수 있으므로 슬롯별로
                # 고유해야 한다. 실제 장소 중복 판정은 place_id로 수행한다.
                candidate_id = (
                    f"{task.slot_id or task.task_id}:restaurant:{raw['restaurant_id']}"
                )
                place = _place(raw, task_id=task.task_id)
                place_lookup[candidate_id] = place
                open_at_visit_time = _restaurant_open_at(raw, visit_date, slot_time)
                reason_facts[candidate_id] = {
                    "domain": "restaurant",
                    "rating": place.rating,
                    "review_count": place.review_count,
                    "open_at_visit_time": open_at_visit_time,
                    "visit_time": slot_time,
                }
                wrapped = _restaurant_group_candidate(raw, include_weather)
                # 슬롯 시각 기준 영업 여부는 검색 후에만 판정되므로 여기서 넣는다.
                if open_at_visit_time:
                    wrapped["payload"]["open_at_visit_time"] = True
                if place.review_count is not None:
                    wrapped["payload"]["review_count"] = place.review_count
                candidates.append(RouteCandidate(
                    candidate_id=candidate_id,
                    domain="restaurant",
                    place_id=str(raw["restaurant_id"]),
                    restaurant_id=str(raw["restaurant_id"]),
                    name=raw["name"],
                    latitude=raw.get("lat"),
                    longitude=raw.get("lng"),
                    payload=wrapped["payload"],
                ))
        elif task.domain == "accommodation":
            for candidate in _route_candidate_window(
                batch.candidates,
                occurrence_index,
            ):
                place = search_candidate_to_place(candidate)
                candidate_id = (
                    f"{task.slot_id or task.task_id}:{task.domain}:{candidate.place_id}"
                )
                place_lookup[candidate_id] = place
                reason_facts[candidate_id] = {"domain": task.domain}
                wrapped = _accommodation_group_candidate(candidate, place)
                candidates.append(RouteCandidate(
                    candidate_id=candidate_id,
                    domain=task.domain,
                    place_id=candidate.place_id,
                    name=candidate.name,
                    latitude=candidate.latitude,
                    longitude=candidate.longitude,
                    payload=wrapped["payload"],
                ))
        else:
            if task.domain == "attraction":
                weather = weather_cache.get(_route_weather_key(
                    body,
                    parsed,
                    task,
                    visit_date,
                    slot_start_times[task.task_id],
                ))
                domain_candidates = (
                    route_attraction_weather_reranker.rerank(
                        batch.candidates,
                        weather,
                        parsed.original_question,
                    )
                    if include_weather and weather is not None
                    else batch.candidates
                )
            else:
                domain_candidates = batch.candidates
            if task.domain == "cafe":
                previous_anchors, next_anchors = _cafe_neighbor_anchor_coordinates(
                    prepared_tasks,
                    batches,
                    prepared_index,
                    slot_start_times,
                )
                domain_candidates = _rank_cafes_for_route(
                    domain_candidates,
                    previous_anchors,
                    next_anchors,
                )
            for candidate in _route_candidate_window(
                domain_candidates,
                occurrence_index,
            ):
                place = search_candidate_to_place(candidate)
                candidate_id = (
                    f"{task.slot_id or task.task_id}:{task.domain}:{candidate.place_id}"
                )
                place_lookup[candidate_id] = place
                reason_facts[candidate_id] = {
                    "domain": task.domain,
                    "rating": place.rating,
                    "review_count": place.review_count,
                    "weather_condition": candidate.signals.get("weather_condition"),
                    "weather_indoor_evidence": bool(
                        candidate.signals.get("weather_indoor_evidence")
                    ),
                    "weather_outdoor_evidence": bool(
                        candidate.signals.get("weather_outdoor_evidence")
                    ),
                }
                candidates.append(RouteCandidate(
                    candidate_id=candidate_id,
                    domain=task.domain,
                    place_id=candidate.place_id,
                    name=candidate.name,
                    latitude=candidate.latitude,
                    longitude=candidate.longitude,
                    payload={
                        "category": candidate.category,
                        # GPT 이유 작성에 쓸 검증된 근거. 없는 값은 넣지 않는다.
                        "rating": place.rating,
                        "review_count": place.review_count,
                        "evidence": candidate.evidence[:3],
                        "fallback_reason": place.reason,
                    },
                ))
        if not candidates:
            # 슬롯 하나가 비었다고 루트 전체를 실패시키지 않는다. 나머지
            # 슬롯으로 일정을 구성하고 몇 곳을 못 채웠는지 안내한다.
            logger.warning(
                "%s 슬롯(%s)의 후보를 찾지 못해 일정에서 제외합니다.",
                task.task_id,
                task.domain,
            )
            skipped_slots.append(task.domain)
            continue
        slot_inputs.append(RouteSlotCandidates(
            slot_id=task.slot_id or task.task_id,
            day_number=day_number,
            date=visit_date,
            start_time=slot_start_times[task.task_id],
            end_date=task.end_date,
            end_time=task.end_time,
            domain=task.domain,
            candidates=candidates,
        ))

    if not slot_inputs:
        raise ValueError("조건에 맞는 후보를 찾지 못해 루트를 만들 수 없습니다.")

    planner_input = RoutePlannerInput(
        language=effective_query_language(parsed),
        original_question=parsed.original_question,
        route_request=route_request,
        slots=slot_inputs,
        weather_by_day=weather_contexts,
        origin_latitude=body.lat,
        origin_longitude=body.lng,
    )
    logger.info(
        "[route-timing] 슬롯 조립·재랭킹 %.2fs (슬롯 %d개)",
        perf_counter() - assembly_started_at,
        len(slot_inputs),
    )
    plan = await _timed(
        "루트 확정(빔서치 최적화 + GPT 요약·이유)",
        asyncio.to_thread(generate_route_plan, planner_input),
    )
    days: list[DayPlan] = []
    route_language = effective_query_language(parsed)
    for day_number in range(1, day_count + 1):
        day_slots: list[TimeSlot] = []
        # 이유 문장의 "직전 일정" 근거는 방문 시각 순서를 따라야 한다.
        previous_place: Place | None = None
        for confirmed in sorted(
            (slot for slot in plan.slots if slot.day_number == day_number),
            key=lambda slot: (slot.start_time, slot.slot_id),
        ):
            selected = place_lookup[confirmed.selected.candidate_id].model_copy(deep=True)
            # 대표 장소는 GPT가 쓴 이유를 우선하고, 누락·실패한 슬롯만
            # 검증된 사실로 만든 결정론적 문장으로 채운다.
            selected.selection_reason = (
                plan.llm_selection_reasons.get(confirmed.slot_id)
                or _route_place_reason(
                    selected,
                    reason_facts.get(confirmed.selected.candidate_id, {}),
                    previous_place,
                    route_language,
                )
            )
            selected.reason = selected.selection_reason
            alternatives: list[Place] = []
            for rank, alternative in enumerate(confirmed.alternatives, start=2):
                place = place_lookup[alternative.candidate.candidate_id].model_copy(deep=True)
                place.rank = rank
                # 대안도 같은 골격으로 설명해야 대표 장소와 나란히 비교된다.
                place.selection_reason = _route_place_reason(
                    place,
                    reason_facts.get(alternative.candidate.candidate_id, {}),
                    previous_place,
                    route_language,
                )
                place.reason = place.selection_reason
                alternatives.append(place)
            selected.rank = 1
            previous_place = selected
            day_slots.append(TimeSlot(
                slot_id=confirmed.slot_id,
                date=confirmed.date.isoformat(),
                time=confirmed.start_time,
                end_date=confirmed.end_date.isoformat() if confirmed.end_date else None,
                end_time=confirmed.end_time,
                category=selected.category,
                place=selected,
                alternatives=alternatives,
            ))
        days.append(DayPlan(day=day_number, theme=plan.title, slots=day_slots))

    logger.info(
        "[route-timing] 총 소요 %.2fs (%d일 / 슬롯 %d개)",
        perf_counter() - route_started_at,
        day_count,
        len(plan.slots),
    )

    if accommodation_place is not None:
        area_centroid = _route_area_centroid(days)
        accommodation_place = _with_accommodation_reason(
            accommodation_place,
            area_centroid,
            route_language,
        )
        accommodation_alternatives = [
            _with_accommodation_reason(place, area_centroid, route_language)
            for place in accommodation_alternatives
        ]

    yield _sse(ChatMetaRoute(
        intent=route_intent,
        days=days,
        tool_results=tool_results,
        total_days=day_count,
        total_places=len(plan.slots),
        route_optimized=plan.route_optimized,
        travel_distance_km=plan.travel_distance_km,
        distance_method=plan.distance_method,
        coordinate_coverage=plan.coordinate_coverage,
        result=route_frontend_response(
            days,
            accommodation=accommodation_place,
            accommodation_alternatives=accommodation_alternatives,
        ),
    ).model_dump())
    note = " 각 방문지의 대안 2곳도 함께 준비했습니다."
    if plan.route_optimized:
        note += " 후보 좌표를 바탕으로 시간순 연속 방문지의 직선거리를 최적화했습니다."
    if include_weather and any(not context.get("available") for context in weather_contexts):
        note += " 제공 범위를 벗어난 예보 시점은 날씨를 추측하지 않고 검색 순위를 유지했습니다."
    if skipped_slots:
        labels = [
            DOMAIN_LABELS.get(domain, {}).get(
                effective_query_language(parsed), domain
            )
            for domain in dict.fromkeys(skipped_slots)
        ]
        note += (
            f" 조건에 맞는 후보를 찾지 못한 {', '.join(labels)}"
            f" {len(skipped_slots)}곳은 일정에서 제외했습니다."
        )
    if has_mock:
        note += " 식당 외 도메인은 현재 임시 후보입니다."
    if day_count > 1 and accommodation_place is None:
        note += " 숙소 후보는 별도 검색에서 찾지 못했습니다."
    yield _sse(ChatToken(text=(plan.summary or "추천 루트를 구성했습니다.") + note).model_dump())
    yield _sse(ChatDone().model_dump())


def _restaurant_group_candidate(candidate: dict, include_weather: bool) -> dict:
    confirmed_features = [
        label
        for field, label in (
            ("has_parking", "parking"),
            ("allows_pets", "pets_allowed"),
            ("has_kids_menu", "kids_menu"),
            ("has_group_seating", "group_seating"),
            ("has_private_room", "private_room"),
            ("has_baby_chair", "baby_chair"),
            ("has_disabled_access", "wheelchair_access"),
        )
        if candidate.get(field) is True
    ]
    payload = {
        "category": candidate.get("category"),
        "rating": candidate.get("rating"),
        "distance_km": candidate.get("distance_km"),
        "opening_status": (
            candidate.get("open_status") if candidate.get("open_status_basis") else None
        ),
        "menu_price_median_krw": candidate.get("menu_price_median"),
        "confirmed_features": confirmed_features,
        "menus": [
            menu.get("menu_name")
            for menu in candidate.get("evidence", {}).get("menus", [])[:3]
        ],
        "reviews": [
            str(review.get("content", ""))[:200]
            for review in candidate.get("evidence", {}).get("reviews", [])[:2]
        ],
    }
    if include_weather:
        payload["weather_reasons"] = candidate.get("weather_reasons", [])
    return {
        "place_id": str(candidate["restaurant_id"]),
        "name": candidate["name"],
        "payload": payload,
        "fallback_reason": (
            "; ".join(candidate.get("weather_reasons", [])[:2])
            if include_weather and candidate.get("weather_reasons")
            else "요청 조건과 식당·리뷰·메뉴 검색 순위를 종합해 선정했습니다."
        ),
        "raw_candidate": candidate,
    }


def _accommodation_group_candidate(candidate, place) -> dict:
    payload = {
        "category": candidate.category,
        "price": candidate.attributes.get("price"),
        "live_rating": candidate.attributes.get("live_rating"),
        "rating": candidate.attributes.get("rating"),
        "review_count": candidate.attributes.get("review_count"),
        "features": candidate.attributes.get("features"),
        "url": candidate.attributes.get("url"),
        "evidence": candidate.evidence[:3] if candidate.evidence else [],
        "fallback_reason": place.reason,
    }
    return {
        "place_id": candidate.place_id,
        "name": candidate.name,
        "payload": payload,
        "fallback_reason": (
            str(candidate.attributes.get("reason") or "").strip()
            or (candidate.evidence[0] if candidate.evidence else "검색 조건 관련도")
        ),
        "raw_candidate": candidate,
    }


async def _multi_task_recommendation_stream(
    body: ChatRequest,
    source_mode: str,
    routing_reason: str,
):
    """Task별 상위 10개를 한 GPT 호출에 보내고 각 그룹에서 3개씩 선택한다."""
    parsed = body.parsed_query
    if parsed is None:
        raise ValueError("복합 Task 추천에는 parsed_query가 필요합니다.")
    canonical_mode = normalize_source_mode(source_mode)
    include_weather = canonical_mode == "rag_mcp"
    if any(task.domain == "restaurant" for task in parsed.tasks):
        weather, tool_results, weather_sources = await _structured_weather(body, canonical_mode)
    else:
        weather, tool_results, weather_sources = None, [], []
    task_groups: list[dict] = []
    requests_by_task = {}
    sources: list[str] = []
    has_mock = False

    for task in parsed.tasks:
        group_candidates: list[dict] = []
        candidate_count = (
            30 if task.domain == "restaurant" else LLM_CANDIDATE_COUNT
        )
        requests_by_task[str(task.task_id)] = build_domain_search_request(
            parsed,
            task,
            latitude=body.lat,
            longitude=body.lng,
            current_location_name=body.location_name,
            candidate_count=candidate_count,
            min_rating=body.min_rating,
        )
        batch = await _search_structured_task(
            body,
            task,
            candidate_count=candidate_count,
        )
        sources.extend(batch.sources)
        has_mock = has_mock or batch.used_mock
        if task.domain == "restaurant":
            candidates = [to_legacy_candidate(item) for item in batch.candidates]
            if include_weather and weather is not None:
                candidates = rerank_with_weather(
                    candidates,
                    weather,
                    parsed.original_question,
                    source_mode="rag_mcp",
                )
            else:
                candidates = prepare_rag_only_candidates(candidates)
            group_candidates = [
                _restaurant_group_candidate(candidate, include_weather)
                for candidate in candidates[:LLM_CANDIDATE_COUNT]
            ]
        elif task.domain == "accommodation":
            group_candidates = [
                _accommodation_group_candidate(candidate, search_candidate_to_place(candidate))
                for candidate in batch.candidates[:LLM_CANDIDATE_COUNT]
            ]
        else:
            candidates, attraction_sources = await _rerank_attraction_candidates(
                batch.candidates,
                parsed,
                canonical_mode,
                requests_by_task[str(task.task_id)],
            ) if task.domain == "attraction" else (batch.candidates, ())
            sources.extend(attraction_sources)
            group_candidates = [
                {
                    "place_id": candidate.place_id,
                    "name": candidate.name,
                    "payload": {
                        "category": candidate.category,
                        "evidence": candidate.evidence[:3],
                        "congestion": {
                            "level": candidate.signals.get("congestion_level"),
                            "score": candidate.signals.get("congestion_score"),
                            "observed_at": candidate.signals.get("congestion_observed_at"),
                        } if candidate.signals.get("congestion_available") else None,
                    },
                    "fallback_reason": (
                        str(candidate.attributes.get("reason") or "").strip()
                        or (candidate.evidence[0] if candidate.evidence else "검색 조건 관련도")
                    ),
                    "raw_candidate": candidate,
                }
                for candidate in candidates[:LLM_CANDIDATE_COUNT]
            ]
        task_groups.append({
            "task_id": task.task_id,
            "domain": task.domain,
            "candidates": group_candidates,
        })

    if not any(group["candidates"] for group in task_groups):
        yield _sse(ChatMetaPlaces(
            intent=mode_to_intent(canonical_mode),
            places=[],
            tool_results=tool_results,
            reasons=[routing_reason],
            sources=list(dict.fromkeys([*sources, *weather_sources])),
            result=recommendation_frontend_response([]),
        ).model_dump())
        empty_message = (
            "I couldn't find any places matching those conditions."
            if effective_query_language(parsed) == "en"
            else "조건에 맞는 장소를 찾지 못했습니다."
        )
        yield _sse(ChatToken(text=empty_message).model_dump())
        yield _sse(ChatDone().model_dump())
        return

    recommendation = await select_grouped_candidates(
        message=body.message,
        language=effective_query_language(parsed),
        task_groups=task_groups,
        requests_by_task=requests_by_task,
        selection_registry=domain_selection_registry,
        common_selector=generate_grouped_recommendation_result,
        weather=weather,
        source_mode=canonical_mode,
    )
    places: list[Place] = []
    selected_weather_reasons: list[str] = []
    for task_result in recommendation["task_results"]:
        task_id = task_result["task_id"]
        domain = task_result["domain"]
        for rank, item in enumerate(task_result["selections"][:GROUP_SELECTION_COUNT], start=1):
            wrapped = item["candidate"]
            reason = item["selection_reason"]
            if domain == "restaurant":
                raw = wrapped["raw_candidate"]
                places.append(_place(
                    raw,
                    rank=rank,
                    selection_reason=reason,
                    task_id=task_id,
                ))
                selected_weather_reasons.extend(raw.get("weather_reasons", []))
            else:
                places.append(search_candidate_to_place(
                    wrapped["raw_candidate"],
                    rank=rank,
                    selection_reason=reason,
                ))

    reasons = [routing_reason, *selected_weather_reasons]
    if has_mock:
        reasons.append("검색기가 없는 도메인은 교체 가능한 임시 고정 후보를 사용했습니다.")
    yield _sse(ChatMetaPlaces(
        intent=mode_to_intent(canonical_mode),
        places=places,
        tool_results=tool_results,
        reasons=list(dict.fromkeys(reasons)),
        sources=list(dict.fromkeys([*sources, *weather_sources])),
        result=recommendation_frontend_response(places),
    ).model_dump())
    answer = recommendation["answer"]
    for start in range(0, len(answer), 32):
        yield _sse(ChatToken(text=answer[start:start + 32]).model_dump())
    yield _sse(ChatDone().model_dump())


async def _restaurant_stream(
    body: ChatRequest,
    source_mode: str,
    routing_reason: str,
    structured_task=None,
):
    canonical_mode = normalize_source_mode(source_mode)
    intent = mode_to_intent(canonical_mode)
    apply_weather_reranking = canonical_mode == "rag_mcp"
    effective_lang = (
        effective_query_language(body.parsed_query)
        if body.parsed_query is not None else body.lang
    )
    effective_place_name = (
        body.parsed_query.filters.location
        or (
            body.parsed_query.weather_request.location_name
            if body.parsed_query.weather_request else None
        )
        or body.location_name
        or "서울"
        if body.parsed_query is not None
        else body.location_name or "서울"
    )
    async def search_candidates():
        if body.parsed_query is not None and structured_task is not None:
            batch = await _search_structured_task(body, structured_task, candidate_count=30)
            result = {
                "candidates": [to_legacy_candidate(item) for item in batch.candidates],
            }
            # 공통 도메인 검색 계약은 후보 목록만 반환하므로, 빈 결과일 때는 명시된
            # 지역의 해석 실패 여부를 복원해 사용자 안내가 일반 조건 불일치로 흐려지지
            # 않게 한다. 주요 권역은 geocode_kakao 내부의 안정 좌표로 즉시 해결된다.
            if not batch.candidates:
                requested_location = effective_task_filters(
                    body.parsed_query, structured_task
                ).location
                if requested_location and await asyncio.to_thread(
                    geocode_kakao, requested_location
                ) is None:
                    result.update({
                        "location_name": requested_location,
                        "location_resolution_failed": True,
                    })
            return result, list(batch.sources)

        result = await asyncio.to_thread(
            search_restaurants,
            body.message,
            body.lang,
            body.min_rating,
            body.open_now,
            2.0,
            30,
        )
        suffix = "en" if str(effective_lang).lower().startswith("en") else "ko"
        return result, [
            f"restaurant_{suffix}",
            f"restaurant_review_{suffix}",
            f"restaurant_menu_{suffix}",
        ]

    async def fetch_weather():
        weather_lat = body.lat
        weather_lng = body.lng
        if not (
            body.location_name
            and weather_lat is not None
            and weather_lng is not None
            and effective_place_name.strip().casefold()
            == body.location_name.strip().casefold()
        ):
            geocoded = await asyncio.to_thread(geocode_kakao, effective_place_name)
            if geocoded is not None:
                weather_lat, weather_lng, _ = geocoded
        weather_lat = weather_lat if weather_lat is not None else SEOUL_CENTER[0]
        weather_lng = weather_lng if weather_lng is not None else SEOUL_CENTER[1]
        weather_request = (
            body.parsed_query.weather_request
            if body.parsed_query is not None else None
        )
        weather = await get_weather_via_mcp(
            body.message,
            weather_lat,
            weather_lng,
            effective_lang,
            effective_place_name,
            target_date=(
                str(weather_request.target_date)
                if weather_request and weather_request.target_date else None
            ) or (
                str(trusted_visit_date(body.parsed_query))
                if body.parsed_query and trusted_visit_date(body.parsed_query) else None
            ),
            target_time=(weather_request.target_time if weather_request else None) or (
                trusted_time_window(body.parsed_query) if body.parsed_query else None
            ),
        )
        return weather, weather_lat, weather_lng

    weather: dict | None = None
    tool_results: list[ToolResult] = []
    if apply_weather_reranking:
        (rag_result, sources), (
            weather,
            weather_lat,
            weather_lng,
        ) = await asyncio.gather(search_candidates(), fetch_weather())
    else:
        rag_result, sources = await search_candidates()

    candidates = rag_result["candidates"]
    if apply_weather_reranking:
        candidates = rerank_with_weather(
            candidates,
            weather,
            body.message,
            source_mode=canonical_mode,
        )
        tool_results.append(
            ToolResult(
                tool_name="get_weather_context",
                params={"lat": weather_lat, "lng": weather_lng, "query": body.message},
                result={key: value for key, value in weather.items() if key != "error"},
                ok=bool(weather.get("available")),
                source="live" if weather.get("available") else "mock",
                error=weather.get("error"),
            )
        )
        sources.append("KMA-via-Weather-MCP")
    else:
        # RAG_ONLY에서는 날씨 조회뿐 아니라 잔존 날씨 점수/사유도 최종 GPT에 전달하지 않는다.
        candidates = prepare_rag_only_candidates(candidates)
    # 단일 식당 추천은 상위 10개를 GPT가 검토해 최종 선택지 3개를 고른다.
    shortlisted = candidates[:LLM_CANDIDATE_COUNT]
    structured_context = None
    if body.parsed_query is not None and structured_task is not None:
        structured_context = {
            "intent": body.parsed_query.intent,
            "normalized_question": body.parsed_query.normalized_question,
            "task": structured_task.model_dump(mode="json"),
            "filters": body.parsed_query.filters.model_dump(mode="json"),
        }

    if not shortlisted:
        yield _sse(ChatMetaPlaces(
            intent=intent,
            places=[],
            tool_results=tool_results,
            reasons=[routing_reason],
            sources=sources,
            result=recommendation_frontend_response([]),
        ).model_dump())
        yield _sse(ChatToken(
            text=_empty_restaurant_message(rag_result, effective_lang)
        ).model_dump())
    else:
        recommendation = await asyncio.to_thread(
            generate_recommendation_result,
            body.message,
            effective_lang,
            shortlisted,
            weather,
            canonical_mode,
            structured_context,
        )
        selections = recommendation["selections"][:FINAL_RECOMMENDATION_COUNT]
        selected_places = [
            _place(
                item["candidate"],
                rank=rank,
                selection_reason=item["selection_reason"],
            )
            for rank, item in enumerate(selections, start=1)
        ]
        yield _sse(ChatMetaPlaces(
            intent=intent,
            places=selected_places,
            tool_results=tool_results,
            reasons=[
                routing_reason,
                *[
                    reason
                    for item in selections
                    for reason in item["candidate"].get("weather_reasons", [])
                ],
            ],
            sources=sources,
            result=recommendation_frontend_response(selected_places),
        ).model_dump())
        answer = recommendation["answer"]
        for start in range(0, len(answer), 32):
            chunk = answer[start:start + 32]
            yield _sse(ChatToken(text=chunk).model_dump())
    yield _sse(ChatDone().model_dump())


def _with_resolved_message(body: ChatRequest) -> ChatRequest:
    if body.parsed_query is None:
        return body
    # 프론트엔드가 마지막 HITL 답변을 message로 보내더라도 다음 모델에는
    # 전체 맥락이 반영된 최종 질문을 전달한다.
    return body.model_copy(
        update={"message": body.parsed_query.normalized_question}
    )


@dataclass(frozen=True)
class _PendingLocationChoice:
    parsed_query: object
    candidates: list


_PENDING_LOCATION_CHOICES: OrderedDict[str, _PendingLocationChoice] = OrderedDict()
_MAX_PENDING_LOCATION_CHOICES = 100


def _store_location_choice(thread_id: str, pending: _PendingLocationChoice) -> None:
    _PENDING_LOCATION_CHOICES[thread_id] = pending
    _PENDING_LOCATION_CHOICES.move_to_end(thread_id)
    while len(_PENDING_LOCATION_CHOICES) > _MAX_PENDING_LOCATION_CHOICES:
        _PENDING_LOCATION_CHOICES.popitem(last=False)


def _selected_location_choice(thread_id: str, answer: str):
    pending = _PENDING_LOCATION_CHOICES.get(thread_id)
    if pending is None:
        return None
    match = re.search(r"\d+", answer)
    if match is None:
        return False
    index = int(match.group()) - 1
    if not 0 <= index < len(pending.candidates):
        return False
    _PENDING_LOCATION_CHOICES.pop(thread_id, None)
    return pending, pending.candidates[index]


async def resolve_travel_query(
    body: ChatRequest,
    *,
    service: TravelQueryService | None = None,
    location_resolver: SearchLocationResolver | None = None,
):
    """원문 채팅을 StructuredTravelQuery로 변환하거나 HITL thread를 재개한다."""
    if body.travel_query_thread_id:
        choice = _selected_location_choice(body.travel_query_thread_id, body.message)
        if choice is False:
            return None, TravelQueryApiResponse(
                thread_id=body.travel_query_thread_id,
                status="collecting",
                assistant_message="후보 번호를 입력해 주세요.",
                missing_fields=["location_choice"],
            )
        if choice is not None:
            pending, selected = choice
            return body.model_copy(update={
                "parsed_query": pending.parsed_query,
                "lat": selected.latitude,
                "lng": selected.longitude,
                "location_name": selected.place_name,
            }), None
    if body.parsed_query is not None:
        return body, None
    else:
        service = service or get_travel_query_service()
        if body.travel_query_thread_id:
            response = await service.resume(body.travel_query_thread_id, body.message)
        else:
            language = "en" if body.lang.lower().startswith("en") else "ko"
            response = await service.start(TravelQueryStartRequest(
                message=body.message,
                language=language,
                lat=body.lat,
                lng=body.lng,
                location_name=body.location_name,
            ))
        if response.status != "ready":
            return None, response
        parsed_query = response.structured_query
        thread_id = response.thread_id

    resolver = location_resolver or SearchLocationResolver()
    resolved = await resolver.resolve(
        location=parsed_query.filters.location,
        latitude=body.lat,
        longitude=body.lng,
        current_location_name=body.location_name,
    )
    if resolved.requires_disambiguation:
        _store_location_choice(thread_id, _PendingLocationChoice(parsed_query, resolved.candidates))
        lines = [
            f"{index}. {candidate.place_name} ({candidate.road_address_name or candidate.address_name or '주소 정보 없음'})"
            for index, candidate in enumerate(resolved.candidates, start=1)
        ]
        prompt = (
            "Which location did you mean? Reply with a number.\n"
            if parsed_query.language == "en"
            else "어느 장소를 말씀하셨나요? 번호로 선택해 주세요.\n"
        )
        return None, TravelQueryApiResponse(
            thread_id=thread_id,
            status="collecting",
            assistant_message=prompt + "\n".join(lines),
            missing_fields=["location_choice"],
        )
    return body.model_copy(update={
        "parsed_query": parsed_query,
        "lat": resolved.latitude,
        "lng": resolved.longitude,
        "location_name": resolved.location_name,
    }), None


async def _stream(body: ChatRequest):
    try:
        body, travel_response = await resolve_travel_query(body)
        if travel_response is not None:
            continuation = {
                "thread_id": travel_response.thread_id,
                "missing_fields": travel_response.missing_fields,
            } if travel_response.status == "collecting" else None
            yield _sse(ChatMetaPlaces(
                intent="chitchat",
                sources=["travel-query"],
                continuation=continuation,
                result=empty_frontend_response("general"),
            ).model_dump())
            yield _sse(ChatToken(text=travel_response.assistant_message or "요청을 처리할 수 없습니다.").model_dump())
            yield _sse(ChatDone().model_dump())
            return
        body = _with_resolved_message(body)
        if body.parsed_intent == "modify_route" or (
            body.parsed_query is not None
            and body.parsed_query.intent == "modify_route"
        ):
            yield _sse(
                ChatMetaPlaces(
                    intent="chitchat",
                ).model_dump()
            )
            yield _sse(
                ChatToken(text=ROUTE_MODIFICATION_UNSUPPORTED_MESSAGE).model_dump()
            )
            yield _sse(ChatDone().model_dump())
            return

        structured_task = None
        if body.parsed_query is not None:
            parsed = deduplicate_recommendation_tasks(body.parsed_query)
            if parsed is not body.parsed_query:
                body = body.model_copy(update={"parsed_query": parsed})
            canonical_mode = derive_source_mode(parsed)
            parsed_intent = parsed.intent
            if parsed_intent in PARSED_INTENT_TO_API_INTENT:
                intent = PARSED_INTENT_TO_API_INTENT[parsed_intent]
            else:
                intent = mode_to_intent(canonical_mode)
            if parsed_intent == "single_place_recommendation" and parsed.tasks:
                structured_task = parsed.tasks[0]
            decision = None
        elif body.parsed_intent:
            if body.parsed_intent in PARSED_INTENT_TO_API_INTENT:
                intent = PARSED_INTENT_TO_API_INTENT[body.parsed_intent]
            else:
                if not body.source_mode:
                    raise ValueError(
                        "상위 TravelQuery를 전달할 때는 parsed_intent와 source_mode를 함께 보내야 합니다."
                    )
                intent = mode_to_intent(body.source_mode)
            decision = None
        else:
            route_intent = classify_intent(body.message, body.lang, body.history)
            if route_intent in ROUTE_INTENTS:
                intent = route_intent
                decision = None
            elif body.source_mode:
                # source_mode만 전달된 과도기 호출도 별도 소스 라우터 GPT 없이 처리한다.
                intent = mode_to_intent(body.source_mode)
                decision = None
            else:
                decision = await decide_source_mode(body.message, body.lang, body.history)
                intent = mode_to_intent(decision.mode)

        if intent in ROUTE_INTENTS:
            if body.parsed_query is not None:
                async for event in _structured_tasks_stream(
                    body,
                    derive_source_mode(body.parsed_query),
                    route_intent=intent,
                ):
                    yield event
                return
            meta = ChatMetaRoute(
                intent=intent,
                days=[],
                total_days=0,
                total_places=0,
                result=empty_frontend_response("error"),
            )
            yield _sse(meta.model_dump())
            yield _sse(ChatToken(text="일정 생성 기능은 아직 연결되지 않았습니다.").model_dump())
            yield _sse(ChatDone().model_dump())
            return

        if intent in {"rag", "both"}:
            selected_mode = (
                derive_source_mode(body.parsed_query)
                if body.parsed_query is not None
                else body.source_mode or decision.mode
            )
            if body.parsed_query is not None and (
                structured_task is None
                or len(body.parsed_query.tasks) > 1
                or structured_task.domain != "restaurant"
            ):
                async for event in _multi_task_recommendation_stream(
                    body,
                    selected_mode,
                    "상위 Structured Query Parser의 Task 그룹을 사용했습니다.",
                ):
                    yield event
                return
            async for event in _restaurant_stream(
                body,
                source_mode=selected_mode,
                routing_reason=(
                    "상위 Structured Query Parser의 Task와 Filter를 사용했습니다."
                    if body.parsed_query is not None
                    else "상위 Structured Query Parser의 source_mode를 사용했습니다."
                    if body.source_mode
                    else decision.reason
                ),
                structured_task=structured_task,
            ):
                yield event
            return

        if intent == "mcp":
            if body.parsed_query is not None:
                weather, tool_results, weather_sources = await _structured_weather(
                    body, "mcp_only"
                )
                effective_lang = effective_query_language(body.parsed_query)
                reason = "상위 Structured Query Parser의 날씨 요청을 사용했습니다."
            else:
                weather_lat = body.lat or SEOUL_CENTER[0]
                weather_lng = body.lng or SEOUL_CENTER[1]
                weather = await get_weather_via_mcp(
                    body.message,
                    weather_lat,
                    weather_lng,
                    body.lang,
                    body.location_name or "서울",
                )
                tool_results = [ToolResult(
                    tool_name="get_weather_context",
                    params={"lat": weather_lat, "lng": weather_lng, "query": body.message},
                    result={key: value for key, value in weather.items() if key != "error"},
                    ok=bool(weather.get("available")),
                    source="live" if weather.get("available") else "mock",
                    error=weather.get("error"),
                )]
                weather_sources = ["KMA-via-Weather-MCP"]
                effective_lang = body.lang
                reason = (
                    "상위 Structured Query Parser의 source_mode를 사용했습니다."
                    if body.source_mode
                    else decision.reason
                )
            meta = ChatMetaPlaces(
                intent="mcp",
                tool_results=tool_results,
                reasons=[reason],
                sources=weather_sources,
                result=empty_frontend_response("weather"),
            )
            yield _sse(meta.model_dump())
            async for chunk in stream_mcp_only_answer(body.message, effective_lang, weather):
                yield _sse(ChatToken(text=chunk).model_dump())
            yield _sse(ChatDone().model_dump())
            return

        meta = ChatMetaPlaces(
            intent=intent,
            result=empty_frontend_response("general"),
        )
        yield _sse(meta.model_dump())
        response_lang = (
            effective_query_language(body.parsed_query)
            if body.parsed_query else body.lang
        )
        response_instruction = (
            body.parsed_query.general_response_instruction
            if body.parsed_query else None
        )
        async for chunk in stream_chat_response(
            body.message,
            response_lang,
            body.history,
            response_instruction,
        ):
            yield _sse(ChatToken(text=chunk).model_dump())
        yield _sse(ChatDone().model_dump())
    except Exception:
        # 실제 예외는 서버 로그에만 남기고, 사용자에게는 내부 정보(도메인명, DB 접속
        # 문자열 등)가 노출되지 않는 일반 안내 메시지를 전달한다.
        logger.exception("POST /chat 처리 중 예외 발생 (message=%r)", body.message)
        yield _sse(ChatError(
            message=_safe_error_message(body.lang),
            result=empty_frontend_response("error"),
        ).model_dump())


@router.post("/chat")
async def chat(body: ChatRequest):
    return StreamingResponse(_stream(body), media_type="text/event-stream")
