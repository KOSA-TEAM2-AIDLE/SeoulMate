import inspect
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from application.recommendation.domain_executor import execute_domain_search
from application.tool_policy import requested_contexts
from domains.cafe.search_service import CafeSearchService
from domains.common.mapper import search_candidate_to_place
from domains.common.models import DomainSearchRequest, SearchCandidate
from domains.common.registry import DomainSearchRegistry
from routers import chat
from routers.chat import _stream
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
        captured = {}

        def choose_first(*args, **kwargs):
            group = args[2][0]
            captured["candidate"] = group["candidates"][0]["raw_candidate"]
            return {
                "answer": "한적한 문화시설 추천",
                "task_results": [{
                    "task_id": group["task_id"],
                    "domain": group["domain"],
                    "selections": [{
                        "candidate": group["candidates"][0],
                        "selection_reason": "혼잡도가 낮습니다.",
                    }],
                }],
            }

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
            patch("routers.chat.generate_grouped_recommendation_result", choose_first),
            patch(
                "integrations.mcp.congestion_client.CongestionMCPProvider.get_context",
                return_value=congestion,
            ) as get_context,
        ):
            events = [event async for event in _stream(body)]

        self.assertTrue(events)
        get_context.assert_awaited_once()
        self.assertGreater(captured["candidate"].final_score, 0.70)
        self.assertEqual(captured["candidate"].signals["congestion_level"], "원활")

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
