"""POST /chat: RAG 30개 → 날씨 재랭킹 → GPT 최종 답변 SSE."""

from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.dependencies import domain_registry
from application.recommendation.domain_executor import execute_domain_search
from application.response.frontend_response_mapper import (
    empty_frontend_response,
    recommendation_frontend_response,
    route_frontend_response,
)
from domains.common.mapper import search_candidate_to_place
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
from schemas.common import Place, ToolResult
from schemas.route_planner import (
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
from services.location import SEOUL_CENTER, geocode_kakao
from services.rag import search_restaurants
from services.query_policy import (
    deduplicate_recommendation_tasks,
    derive_source_mode,
    effective_query_language,
    trusted_time_window,
    trusted_visit_date,
)
from domains.restaurant.weather_policy import prepare_rag_only_candidates, rerank_with_weather
from services.source_router import decide_source_mode, mode_to_intent, normalize_source_mode
from integrations.mcp.weather_client import get_weather_via_mcp
from application.route.route_planner import generate_route_plan


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


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _empty_restaurant_message(rag_result: dict, language: str) -> str:
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
    if parsed and location_name and not same_as_current:
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

    weather, tool_results, weather_sources = await _structured_weather(body, source_mode)
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
            count = min(max(task.desired_count, 1), 3)
            places.extend(
                search_candidate_to_place(candidate)
                for candidate in batch.candidates[:count]
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


async def _structured_route_stream(body: ChatRequest, source_mode: str, route_intent: str):
    """Task별 5개 후보를 GPT가 대표 1곳과 대안 2곳으로 편성한다."""
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
    weather_cache: dict[tuple[str, str], dict] = {}
    weather_contexts: list[dict] = []
    weather_location = parsed.filters.location or body.location_name or "서울"
    weather_lat, weather_lng = body.lat, body.lng
    same_as_current = bool(
        body.location_name
        and weather_location.strip().lower() == body.location_name.strip().lower()
    )
    if include_weather and not same_as_current:
        geocoded = await asyncio.to_thread(geocode_kakao, weather_location)
        if geocoded:
            weather_lat, weather_lng, weather_location = geocoded
        else:
            weather_lat, weather_lng = None, None
    weather_lat = weather_lat if weather_lat is not None else SEOUL_CENTER[0]
    weather_lng = weather_lng if weather_lng is not None else SEOUL_CENTER[1]

    slot_inputs: list[RouteSlotCandidates] = []
    place_lookup: dict[str, Place] = {}
    has_mock = False
    per_day_counts: dict[int, int] = {}
    for index, task in enumerate(parsed.tasks, start=1):
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
        candidates: list[RouteCandidate] = []
        batch = await _search_structured_task(
            body,
            task,
            candidate_count=30 if task.domain == "restaurant" else 5,
        )
        has_mock = has_mock or batch.used_mock
        if task.domain == "restaurant":
            slot_time = task.start_time or DOMAIN_DEFAULT_TIMES.get(task.domain, "16:00")
            weather = None
            if include_weather:
                cache_key = (visit_date.isoformat(), slot_time)
                weather = weather_cache.get(cache_key)
                if weather is None:
                    weather = await get_weather_via_mcp(
                        parsed.original_question,
                        weather_lat,
                        weather_lng,
                        effective_query_language(parsed),
                        weather_location,
                        target_date=visit_date.isoformat(),
                        target_time=slot_time,
                    )
                    weather_cache[cache_key] = weather
                    weather_contexts.append(weather)
                    tool_results.append(ToolResult(
                        tool_name="get_weather_context",
                        params={"lat": weather_lat, "lng": weather_lng, "target_date": visit_date.isoformat(), "target_time": slot_time},
                        result={key: value for key, value in weather.items() if key != "error"},
                        ok=bool(weather.get("available")),
                        source="live" if weather.get("available") else "mock",
                        error=weather.get("error"),
                    ))
            ranked = [to_legacy_candidate(item) for item in batch.candidates]
            ranked = (
                rerank_with_weather(ranked, weather, parsed.original_question, source_mode="rag_mcp")
                if include_weather and weather is not None
                else prepare_rag_only_candidates(ranked)
            )
            for raw in ranked[:5]:
                # candidate_id는 플래너가 한 슬롯의 후보를 고르는 실행용 ID다.
                # 같은 식당이 점심/저녁 양쪽 후보에 포함될 수 있으므로 슬롯별로
                # 고유해야 한다. 실제 장소 중복 판정은 place_id로 수행한다.
                candidate_id = (
                    f"{task.slot_id or task.task_id}:restaurant:{raw['restaurant_id']}"
                )
                place = _place(raw, task_id=task.task_id)
                place_lookup[candidate_id] = place
                wrapped = _restaurant_group_candidate(raw, include_weather)
                candidates.append(RouteCandidate(
                    candidate_id=candidate_id,
                    domain="restaurant",
                    place_id=str(raw["restaurant_id"]),
                    restaurant_id=str(raw["restaurant_id"]),
                    name=raw["name"],
                    payload=wrapped["payload"],
                ))
        else:
            for candidate in batch.candidates[:5]:
                place = search_candidate_to_place(candidate)
                candidate_id = (
                    f"{task.slot_id or task.task_id}:{task.domain}:{candidate.place_id}"
                )
                place_lookup[candidate_id] = place
                candidates.append(RouteCandidate(
                    candidate_id=candidate_id,
                    domain=task.domain,
                    place_id=candidate.place_id,
                    name=candidate.name,
                    payload={
                        "category": candidate.category,
                        "evidence": candidate.evidence[:3],
                        "fallback_reason": place.reason,
                    },
                ))
        if not candidates:
            raise ValueError(f"{task.task_id} 슬롯의 후보를 찾지 못했습니다.")
        slot_inputs.append(RouteSlotCandidates(
            slot_id=task.slot_id or task.task_id,
            day_number=day_number,
            date=visit_date,
            start_time=task.start_time or DOMAIN_DEFAULT_TIMES.get(task.domain, "16:00"),
            end_date=task.end_date,
            end_time=task.end_time,
            domain=task.domain,
            candidates=candidates,
        ))

    planner_input = RoutePlannerInput(
        language=effective_query_language(parsed),
        original_question=parsed.original_question,
        route_request=route_request,
        slots=slot_inputs,
        weather_by_day=weather_contexts,
    )
    plan = await asyncio.to_thread(generate_route_plan, planner_input)
    days: list[DayPlan] = []
    for day_number in range(1, day_count + 1):
        day_slots: list[TimeSlot] = []
        for confirmed in (slot for slot in plan.slots if slot.day_number == day_number):
            selected = place_lookup[confirmed.selected.candidate_id].model_copy(deep=True)
            selected.selection_reason = confirmed.selection_reason
            selected.reason = confirmed.selection_reason
            alternatives: list[Place] = []
            for rank, alternative in enumerate(confirmed.alternatives, start=2):
                place = place_lookup[alternative.candidate.candidate_id].model_copy(deep=True)
                place.rank = rank
                place.selection_reason = alternative.selection_reason
                place.reason = alternative.selection_reason
                alternatives.append(place)
            selected.rank = 1
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

    yield _sse(ChatMetaRoute(
        intent=route_intent,
        days=days,
        tool_results=tool_results,
        total_days=day_count,
        total_places=len(plan.slots),
        result=route_frontend_response(days),
    ).model_dump())
    note = " 각 방문지의 대안 2곳도 함께 준비했습니다."
    if include_weather and any(not context.get("available") for context in weather_contexts):
        note += " 제공 범위를 벗어난 예보 시점은 날씨를 추측하지 않고 검색 순위를 유지했습니다."
    if has_mock:
        note += " 식당 외 도메인은 현재 임시 후보입니다."
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
    weather, tool_results, weather_sources = await _structured_weather(body, canonical_mode)
    task_groups: list[dict] = []
    sources: list[str] = []
    has_mock = False

    for task in parsed.tasks:
        group_candidates: list[dict] = []
        batch = await _search_structured_task(
            body,
            task,
            candidate_count=30 if task.domain == "restaurant" else LLM_CANDIDATE_COUNT,
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
        else:
            group_candidates = [
                {
                    "place_id": candidate.place_id,
                    "name": candidate.name,
                    "payload": {
                        "category": candidate.category,
                        "evidence": candidate.evidence[:3],
                    },
                    "fallback_reason": (
                        str(candidate.attributes.get("reason") or "").strip()
                        or (candidate.evidence[0] if candidate.evidence else "검색 조건 관련도")
                    ),
                    "raw_candidate": candidate,
                }
                for candidate in batch.candidates[:LLM_CANDIDATE_COUNT]
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
        yield _sse(ChatToken(text="조건에 맞는 장소를 찾지 못했습니다.").model_dump())
        yield _sse(ChatDone().model_dump())
        return

    recommendation = await asyncio.to_thread(
        generate_grouped_recommendation_result,
        body.message,
        effective_query_language(parsed),
        task_groups,
        weather,
        canonical_mode,
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
    if body.parsed_query is not None and structured_task is not None:
        batch = await _search_structured_task(body, structured_task, candidate_count=30)
        rag_result = {
            "candidates": [to_legacy_candidate(item) for item in batch.candidates],
        }
        sources = list(batch.sources)
    else:
        rag_result = await asyncio.to_thread(
            search_restaurants,
            body.message,
            body.lang,
            body.min_rating,
            body.open_now,
            2.0,
            30,
        )
        suffix = "en" if str(effective_lang).lower().startswith("en") else "ko"
        sources = [
            f"restaurant_{suffix}",
            f"restaurant_review_{suffix}",
            f"restaurant_menu_{suffix}",
        ]
    candidates = rag_result["candidates"]
    weather_lat = rag_result.get("origin_lat") or body.lat or SEOUL_CENTER[0]
    weather_lng = rag_result.get("origin_lng") or body.lng or SEOUL_CENTER[1]
    weather: dict | None = None
    tool_results: list[ToolResult] = []
    if apply_weather_reranking:
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


async def _stream(body: ChatRequest):
    try:
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
            restaurant_tasks = [task for task in parsed.tasks if task.domain == "restaurant"]
            if parsed_intent == "single_place_recommendation" and restaurant_tasks:
                structured_task = restaurant_tasks[0]
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
                structured_task is None or len(body.parsed_query.tasks) > 1
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
    except Exception as exc:
        yield _sse(ChatError(
            message=str(exc),
            result=empty_frontend_response("error"),
        ).model_dump())


@router.post("/chat")
async def chat(body: ChatRequest):
    return StreamingResponse(_stream(body), media_type="text/event-stream")
