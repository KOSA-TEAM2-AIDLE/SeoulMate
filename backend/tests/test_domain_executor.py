import inspect
import asyncio
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import psycopg2

from application.recommendation.domain_executor import execute_domain_search
from application.recommendation.selection_models import (
    CandidateSelection,
    CandidateSelectionResult,
)
from application.tool_policy import requested_contexts
from domains.cafe.search_service import CafeSearchService
from domains.common.mapper import search_candidate_to_place
from domains.common.models import DomainSearchRequest, SearchCandidate
from domains.common.registry import DomainSearchRegistry
from domains.restaurant.mapper import to_search_candidate as restaurant_to_search_candidate
from routers import chat
from routers.chat import (
    _place,
    _rank_cafes_for_route,
    _rank_restaurants_for_route,
    _restaurant_candidates_open_at_slot,
    _route_candidate_occurrence_key,
    _route_candidate_window,
    _route_search_concurrency,
    _search_route_batches,
    _stream,
)
from schemas.chat import ChatRequest
from schemas.structured_query import StructuredTravelQuery
from integrations.mcp.base_client import ContextResult


def cafe_query() -> StructuredTravelQuery:
    return StructuredTravelQuery.model_validate({
        "language": "ko",
        "intent": "single_place_recommendation",
        "original_question": "성수에서 조용한 카페 추천해줘",
        "normalized_question": "성수 조용한 카페",
        "tasks": [{
            "task_id": "cafe-1",
            "domain": "cafe",
            "search_query": "성수 조용한 카페",
            "themes": ["조용한"],
            "desired_count": 3,
        }],
        "filters": {"location": "성수"},
    })


class LiveCafeService:
    domain = "cafe"
    implemented = True

    async def search(self, request: DomainSearchRequest) -> list[SearchCandidate]:
        self.last_request = request
        return [SearchCandidate(
            domain="cafe",
            place_id="CAFE-REAL-101",
            task_id=request.task_id,
            name="검증된 실제 카페",
            category="카페",
            latitude=37.544,
            longitude=127.056,
            base_score=0.82,
            final_score=0.91,
            evidence=["조용한 좌석이 확인됨"],
            attributes={
                "address": "서울 성동구 테스트로 1",
                "rating": 4.7,
                "review_count": 321,
                "image_url": "https://example.com/cafe.jpg",
            },
        )]


class BrokenCafeService:
    domain = "cafe"
    implemented = True

    async def search(self, request: DomainSearchRequest) -> list[SearchCandidate]:
        raise RuntimeError("cafe database unavailable")


class UnavailableDatabaseCafeService:
    domain = "cafe"
    implemented = True

    async def search(self, request: DomainSearchRequest) -> list[SearchCandidate]:
        raise psycopg2.OperationalError("connection refused")


class LiveAttractionService:
    domain = "attraction"
    implemented = True

    async def search(self, request: DomainSearchRequest) -> list[SearchCandidate]:
        return [SearchCandidate(
            domain="attraction",
            place_id="ATTRACTION-101",
            task_id=request.task_id,
            name="한적한 문화시설",
            category="문화시설",
            latitude=37.5796,
            longitude=126.9770,
            base_score=0.70,
            final_score=0.70,
            evidence=["경복궁 인근 문화시설"],
        )]


class DomainExecutorTests(unittest.IsolatedAsyncioTestCase):
    def test_route_candidate_occurrence_continues_across_days(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "multi_day_route",
            "original_question": "강남구 이틀 루트",
            "normalized_question": "강남구 이틀 루트",
            "tasks": [
                {
                    "task_id": "day-1-a",
                    "domain": "attraction",
                    "search_query": "강남구 명소",
                    "day_number": 1,
                    "filters": {"location": "강남구"},
                },
                {
                    "task_id": "day-1-b",
                    "domain": "attraction",
                    "search_query": "강남구 명소",
                    "day_number": 1,
                    "filters": {"location": "강남구"},
                },
                {
                    "task_id": "day-2-a",
                    "domain": "attraction",
                    "search_query": "강남구 명소",
                    "day_number": 2,
                    "filters": {"location": "강남구"},
                },
            ],
            "filters": {"location": "서울"},
        })

        first, repeated, next_day = parsed.tasks
        self.assertEqual(
            _route_candidate_occurrence_key(first),
            _route_candidate_occurrence_key(repeated),
        )
        # 날짜가 키에 들어가면 Day마다 후보 창이 0으로 돌아가 같은 검색이
        # 매일 같은 상위 후보를 받고, 같은 장소가 여러 날에 배치된다.
        self.assertEqual(
            _route_candidate_occurrence_key(first),
            _route_candidate_occurrence_key(next_day),
        )

    def test_repeated_search_across_days_gets_distinct_candidates(self):
        candidates = list(range(14))
        # 3일치 동일 검색이면 창이 0,1,2로 이동해 대표 후보가 달라져야 한다.
        windows = [_route_candidate_window(candidates, index) for index in range(3)]
        self.assertEqual([window[0] for window in windows], [0, 1, 2])
        self.assertEqual(len({window[0] for window in windows}), 3)

    async def test_route_search_concurrency_follows_busiest_day(self):
        relaxed_tasks = [SimpleNamespace(day_number=day) for day in (1, 1, 1, 2, 2, 2)]
        normal_tasks = [
            SimpleNamespace(day_number=day)
            for day in (1, 1, 1, 1, 1, 2, 2, 2, 2, 2)
        ]

        self.assertEqual(3, _route_search_concurrency(relaxed_tasks, 5))
        self.assertEqual(5, _route_search_concurrency(normal_tasks, 5))
        self.assertEqual(4, _route_search_concurrency(normal_tasks, 4))

    async def test_route_search_batches_are_bounded_and_keep_task_order(self):
        active = 0
        maximum_active = 0

        async def fake_search(_body, task, *, candidate_count):
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            await asyncio.sleep((6 - int(task.task_id)) * 0.001)
            active -= 1
            return (task.task_id, candidate_count)

        prepared = [
            (
                SimpleNamespace(task_id=str(index), domain="cafe"),
                1,
                None,
                index - 1,
                7,
            )
            for index in range(1, 6)
        ]
        with patch("routers.chat._search_structured_task", side_effect=fake_search):
            results = await _search_route_batches(object(), prepared, 3)

        self.assertEqual(3, maximum_active)
        self.assertEqual(["1", "2", "3", "4", "5"], [item[0] for item in results])

    async def test_route_search_batches_share_same_day_restaurant_search_only(self):
        calls = []

        async def fake_search(_body, task, *, candidate_count):
            calls.append(task.task_id)
            return (task.task_id, candidate_count)

        def prepared(task_id, domain, day, query, start_time):
            return (
                SimpleNamespace(
                    task_id=task_id,
                    domain=domain,
                    search_query=query,
                    themes=[],
                    filters=None,
                    start_time=start_time,
                ),
                day,
                f"2026-08-0{day}",
                0,
                6,
            )

        tasks = [
            prepared("lunch-1", "restaurant", 1, "강남구 식당", "12:30"),
            prepared("dinner-1", "restaurant", 1, "강남구 식당", "19:00"),
            prepared("attraction-1", "attraction", 1, "강남구 관광지", "10:00"),
            prepared("attraction-2", "attraction", 1, "강남구 관광지", "17:00"),
            prepared("lunch-2", "restaurant", 2, "마포구 식당", "12:30"),
            prepared("dinner-2", "restaurant", 2, "마포구 식당", "19:00"),
        ]

        with patch("routers.chat._search_structured_task", side_effect=fake_search):
            results = await _search_route_batches(object(), tasks, 5)

        self.assertEqual(
            ["lunch-1", "attraction-1", "attraction-2", "lunch-2"],
            calls,
        )
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[4], results[5])

    async def test_restaurant_candidates_are_filtered_for_each_slot_time(self):
        candidates = [
            {"restaurant_id": 1, "hours": "토 11:00~15:00"},
            {"restaurant_id": 2, "hours": "토 17:00~23:00"},
            {"restaurant_id": 3, "hours": None},
        ]

        lunch = _restaurant_candidates_open_at_slot(
            candidates,
            datetime(2026, 8, 1).date(),
            "12:30",
        )
        dinner = _restaurant_candidates_open_at_slot(
            candidates,
            datetime(2026, 8, 1).date(),
            "19:00",
        )

        self.assertEqual([1, 3], [item["restaurant_id"] for item in lunch])
        self.assertEqual([2, 3], [item["restaurant_id"] for item in dinner])

    async def test_route_restaurants_prefer_anchors_within_two_point_five_km(self):
        anchor = [(37.5, 127.0)]
        candidates = [
            {"restaurant_id": 1, "lat": 37.535, "lng": 127.0},
            {"restaurant_id": 2, "lat": 37.505, "lng": 127.0},
            {"restaurant_id": 3, "lat": 37.507, "lng": 127.0},
            {"restaurant_id": 4, "lat": 37.509, "lng": 127.0},
            {"restaurant_id": 5, "lat": 37.511, "lng": 127.0},
            {"restaurant_id": 6, "lat": 37.513, "lng": 127.0},
        ]

        ranked = _rank_restaurants_for_route(candidates, anchor)

        self.assertEqual(
            [2, 3, 4, 5, 6],
            [item["restaurant_id"] for item in ranked[:5]],
        )
        self.assertTrue(all(
            item["route_anchor_distance_km"] <= 2.5
            for item in ranked[:5]
        ))

    async def test_route_cafes_prefer_a_place_close_to_both_neighbor_attractions(self):
        candidates = [
            SearchCandidate(
                domain="cafe",
                place_id="near-previous-only",
                task_id="cafe-1",
                name="앞 관광지에만 가까운 카페",
                category="카페",
                latitude=37.501,
                longitude=127.0,
                base_score=0.95,
                final_score=0.95,
            ),
            SearchCandidate(
                domain="cafe",
                place_id="between",
                task_id="cafe-1",
                name="두 관광지 사이 카페",
                category="카페",
                latitude=37.510,
                longitude=127.0,
                base_score=0.90,
                final_score=0.90,
            ),
            SearchCandidate(
                domain="cafe",
                place_id="far",
                task_id="cafe-1",
                name="먼 카페",
                category="카페",
                latitude=37.550,
                longitude=127.0,
                base_score=0.99,
                final_score=0.99,
            ),
        ]

        ranked = _rank_cafes_for_route(
            candidates,
            previous_anchors=[(37.500, 127.0)],
            next_anchors=[(37.520, 127.0)],
        )

        self.assertEqual("between", ranked[0].place_id)
        self.assertLessEqual(
            ranked[0].signals["route_previous_distance_km"],
            1.5,
        )
        self.assertLessEqual(
            ranked[0].signals["route_next_distance_km"],
            1.5,
        )

    async def test_legacy_restaurant_place_preserves_tripadvisor_link(self):
        restaurant = _place({
            "restaurant_id": 101,
            "name": "검증 식당",
            "category": "한식",
            "score": 0.9,
            "link": "https://www.tripadvisor.co.kr/Restaurant_Review-test.html",
        })

        self.assertEqual(
            "https://www.tripadvisor.co.kr/Restaurant_Review-test.html",
            restaurant.link,
        )

    async def test_restaurant_tripadvisor_link_reaches_common_place(self):
        candidate = restaurant_to_search_candidate(
            {
                "restaurant_id": 101,
                "name": "검증 식당",
                "category": "한식",
                "score": 0.9,
                "link": "https://www.tripadvisor.co.kr/Restaurant_Review-test.html",
            },
            "restaurant-1",
        )

        place = search_candidate_to_place(candidate)

        self.assertEqual(
            "https://www.tripadvisor.co.kr/Restaurant_Review-test.html",
            place.link,
        )

    def test_cafe_review_link_reaches_common_place(self):
        candidate = SearchCandidate(
            domain="cafe",
            place_id="cafe-10",
            task_id="task-cafe",
            name="테스트 카페",
            category="카페",
            base_score=0.9,
            final_score=0.9,
            attributes={
                "link": "https://www.tripadvisor.com/Cafe_Review-test.html",
            },
        )

        place = search_candidate_to_place(candidate)

        self.assertEqual(
            "https://www.tripadvisor.com/Cafe_Review-test.html",
            place.link,
        )

    async def test_attraction_congestion_is_candidate_specific_not_generic_weather(self):
        self.assertEqual(requested_contexts("rag_mcp", "attraction"), ())

    async def test_chat_low_congestion_attraction_reranks_static_candidates(self):
        registry = DomainSearchRegistry()
        registry.register(LiveAttractionService())
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "single_place_recommendation",
            "original_question": "경복궁 근처 한적한 문화시설 추천",
            "normalized_question": "경복궁 한적한 문화시설",
            "tasks": [{
                "task_id": "attraction-1",
                "domain": "attraction",
                "search_query": "경복궁 한적한 문화시설",
                "themes": ["한적한", "문화시설"],
                "desired_count": 3,
            }],
            "filters": {"location": "경복궁"},
        })
        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
        congestion = ContextResult(
            provider="congestion",
            available=True,
            data={"congestion": {
                "congestion_score": 20,
                "congestion_level": "원활",
                "observed_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        with (
            patch("routers.chat.domain_registry", registry),
            patch(
                "routers.chat.generate_grouped_recommendation_result",
                side_effect=AssertionError(
                    "관광 단일 추천은 공통 GPT를 호출하면 안 됩니다."
                ),
            ) as common_gpt,
            patch(
                "domains.attraction.selection_service."
                "AttractionSelectionService.select",
                return_value=CandidateSelectionResult(
                    answer="한적한 문화시설 추천",
                    selections=[CandidateSelection(
                        place_id="ATTRACTION-101",
                        selection_reason="혼잡도가 낮습니다.",
                    )],
                ),
            ) as dspy_selector,
            patch(
                "integrations.mcp.congestion_client.CongestionMCPProvider.get_context",
                return_value=congestion,
            ) as get_context,
        ):
            events = [event async for event in _stream(body)]

        self.assertTrue(events)
        common_gpt.assert_not_called()
        dspy_selector.assert_awaited_once()
        get_context.assert_awaited_once()
        request, candidates = dspy_selector.await_args.args
        self.assertEqual(request.task_id, "attraction-1")
        self.assertEqual(request.location, "경복궁")
        self.assertGreater(candidates[0].final_score, 0.70)
        self.assertEqual(candidates[0].signals["congestion_level"], "원활")
        meta = json.loads(events[0].removeprefix("data: "))
        self.assertEqual(meta["places"][0]["source_id"], "ATTRACTION-101")
        self.assertEqual(
            meta["result"]["recommendList"][0]["selectionReason"],
            "혼잡도가 낮습니다.",
        )

    async def test_live_service_preserves_real_domain_id_and_verified_fields(self):
        registry = DomainSearchRegistry()
        registry.register(LiveCafeService())
        parsed = cafe_query()

        batch = await execute_domain_search(
            registry,
            parsed,
            parsed.tasks[0],
            latitude=37.5,
            longitude=127.0,
            candidate_count=5,
            min_rating=4.0,
        )
        place = search_candidate_to_place(batch.candidates[0], rank=1)

        self.assertFalse(batch.used_mock)
        self.assertEqual(batch.sources, ["cafe-search-service"])
        self.assertEqual(place.source_id, "CAFE-REAL-101")
        self.assertIsNone(place.restaurant_id)
        self.assertEqual(place.address, "서울 성동구 테스트로 1")
        self.assertEqual(place.rating, 4.7)
        self.assertEqual(place.review_count, 321)
        self.assertEqual((37.5, 127.0), (registry.get("cafe").last_request.latitude, registry.get("cafe").last_request.longitude))
        self.assertEqual("성수", registry.get("cafe").last_request.location)

    async def test_default_cafe_service_is_no_longer_a_mock_fallback(self):
        registry = DomainSearchRegistry()
        service = CafeSearchService()
        registry.register(service)
        parsed = cafe_query()

        with patch.object(
            service,
            "search",
            return_value=[
                SearchCandidate(
                    domain="cafe",
                    place_id="CAFE-LIVE-1",
                    task_id="cafe-1",
                    name="실제 카페",
                    category="카페",
                    base_score=0.8,
                    final_score=0.8,
                )
            ],
        ):
            batch = await execute_domain_search(
                registry,
                parsed,
                parsed.tasks[0],
            )

        self.assertFalse(batch.used_mock)
        self.assertEqual(batch.sources, ["cafe-search-service"])
        self.assertEqual("CAFE-LIVE-1", batch.candidates[0].place_id)

    async def test_live_service_failure_is_not_hidden_by_mock(self):
        registry = DomainSearchRegistry()
        registry.register(BrokenCafeService())
        parsed = cafe_query()

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            await execute_domain_search(registry, parsed, parsed.tasks[0])

    async def test_unavailable_database_uses_explicit_mock_fallback(self):
        registry = DomainSearchRegistry()
        registry.register(UnavailableDatabaseCafeService())
        parsed = cafe_query()

        batch = await execute_domain_search(registry, parsed, parsed.tasks[0])

        self.assertTrue(batch.used_mock)
        self.assertEqual(batch.sources, ["mock-cafe-agent"])
        self.assertEqual(batch.warnings, ["connection refused"])

    async def test_chat_response_keeps_live_domain_id_and_source(self):
        registry = DomainSearchRegistry()
        registry.register(LiveCafeService())
        parsed = cafe_query()
        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)

        def choose_first(*args, **kwargs):
            group = args[2][0]
            return {
                "answer": "실제 카페 추천 결과",
                "task_results": [{
                    "task_id": group["task_id"],
                    "domain": group["domain"],
                    "selections": [{
                        "candidate": group["candidates"][0],
                        "selection_reason": "요청한 조용한 분위기가 확인됐습니다.",
                    }],
                }],
            }

        with (
            patch("routers.chat.domain_registry", registry),
            patch("routers.chat.generate_grouped_recommendation_result", choose_first),
        ):
            events = [event async for event in _stream(body)]

        meta = json.loads(events[0].removeprefix("data: "))
        self.assertEqual(meta["places"][0]["source_id"], "CAFE-REAL-101")
        self.assertEqual(meta["result"]["recommendList"][0]["id"], "CAFE-REAL-101")
        self.assertIn("cafe-search-service", meta["sources"])
        self.assertNotIn("mock-cafe-agent", meta["sources"])

    def test_chat_router_does_not_call_domain_mock_or_structured_rag_directly(self):
        source = inspect.getsource(chat)
        self.assertNotIn("mock_places_for_task", source)
        self.assertNotIn("search_restaurants_structured", source)


if __name__ == "__main__":
    unittest.main()
