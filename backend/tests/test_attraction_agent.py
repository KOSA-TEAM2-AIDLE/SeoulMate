import unittest

from domains.attraction.agent import AttractionAgent
from domains.attraction.answer_models import (
    AttractionAnswerResult,
    AttractionSelection,
)
from domains.attraction.recommendation_pipeline import (
    AttractionRecommendationResult,
)
from domains.common.models import SearchCandidate
from application.recommendation.location_resolution import ResolvedSearchLocation
from schemas.travel_query_api import (
    TravelQueryApiResponse,
    TravelQueryExecutionContext,
)


def _response(
    *,
    status: str = "ready",
    question: str = "경복궁 근처 관광지와 식당을 추천해줘",
    location: str = "경복궁",
    execution_context: TravelQueryExecutionContext | None = None,
) -> TravelQueryApiResponse:
    values = {
        "thread_id": "attraction-agent-thread",
        "status": status,
    }
    if status == "ready":
        values["structured_query"] = {
            "language": "ko",
            "intent": "day_trip_route",
            "original_question": question,
            "normalized_question": "경복궁 인근 관광지와 식당 추천",
            "tasks": [
                {
                    "task_id": "task_1",
                    "domain": "attraction",
                    "search_query": "경복궁 근처 역사 관광지",
                    "themes": ["역사", "문화"],
                    "desired_count": 3,
                    "visit_date": "2026-07-16",
                },
                {
                    "task_id": "task_2",
                    "domain": "restaurant",
                    "search_query": "경복궁 근처 식당",
                    "desired_count": 1,
                },
            ],
            "filters": {
                "location": location,
                "radius_km": 2.5,
                "start_date": "2026-07-16",
            },
        }
    else:
        values.update({
            "assistant_message": "어느 지역에서 찾을까요?",
            "missing_fields": ["filters.location"],
        })
    response = TravelQueryApiResponse.model_validate(values)
    if execution_context is not None:
        response.execution_context = execution_context
    return response


class RecordingPipeline:
    def __init__(self) -> None:
        self.requests = []

    async def recommend(self, request, *, use_congestion=False):
        self.requests.append((request, use_congestion))
        candidate = SearchCandidate(
            domain="attraction",
            place_id="palace-1",
            task_id=request.task_id,
            name="경복궁",
            category="역사관광",
            base_score=0.9,
            final_score=0.95,
        )
        return AttractionRecommendationResult(
            answer=AttractionAnswerResult(
                answer="경복궁 근처 관광지 세 곳을 추천합니다.",
                selections=[
                    AttractionSelection(
                        place_id="palace-1",
                        selection_reason="질문과 가장 잘 맞습니다.",
                    )
                ],
            ),
            candidates=[candidate],
        )


class AttractionAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_executes_only_attraction_tasks_with_structured_filters(self):
        class Resolver:
            async def resolve(self, **kwargs):
                return ResolvedSearchLocation(
                    location_name=kwargs["location"],
                    latitude=37.5796,
                    longitude=126.977,
                    source="test",
                )

        pipeline = RecordingPipeline()
        agent = AttractionAgent(
            pipeline=pipeline,
            location_resolver=Resolver(),
        )

        result = await agent.execute(_response())

        self.assertEqual("attraction", result.domain)
        self.assertEqual(["task_1"], result.task_ids)
        self.assertEqual(
            "경복궁 근처 관광지 세 곳을 추천합니다.",
            result.assistant_message,
        )
        self.assertEqual(["palace-1"], [item.place_id for item in result.candidates])
        self.assertIsInstance(result.candidates[0], SearchCandidate)
        self.assertEqual(1, len(pipeline.requests))
        request, use_congestion = pipeline.requests[0]
        self.assertEqual("task_1", request.task_id)
        self.assertEqual("attraction", request.domain)
        self.assertEqual("ko", request.language)
        self.assertEqual("경복궁 근처 역사 관광지", request.search_query)
        self.assertEqual(["역사", "문화"], request.themes)
        self.assertEqual("경복궁", request.location)
        self.assertEqual(2.5, request.radius_km)
        self.assertEqual("2026-07-16", request.visit_date.isoformat())
        self.assertTrue(use_congestion)

    async def test_current_location_uses_request_coordinates_and_mcp(self):
        class Resolver:
            async def resolve(self, **kwargs):
                raise AssertionError("현재 좌표는 재해석하면 안 됩니다.")

        pipeline = RecordingPipeline()
        agent = AttractionAgent(pipeline=pipeline, location_resolver=Resolver())
        response = _response(
            question="내 주변 3km 이내 관광지 추천해줘",
            location="서울시청",
            execution_context=TravelQueryExecutionContext(
                latitude=37.5796,
                longitude=126.977,
                location_name="서울시청",
            ),
        )

        await agent.execute(response)

        request, use_congestion = pipeline.requests[0]
        self.assertEqual(37.5796, request.latitude)
        self.assertEqual(126.977, request.longitude)
        self.assertTrue(use_congestion)

    async def test_named_location_is_resolved_before_search_and_uses_mcp(self):
        class Resolver:
            async def resolve(self, **kwargs):
                self.kwargs = kwargs
                return ResolvedSearchLocation(
                    location_name="경복궁",
                    latitude=37.5796,
                    longitude=126.977,
                    source="kakao",
                )

        resolver = Resolver()
        pipeline = RecordingPipeline()
        agent = AttractionAgent(pipeline=pipeline, location_resolver=resolver)

        await agent.execute(_response())

        request, use_congestion = pipeline.requests[0]
        self.assertEqual("경복궁", resolver.kwargs["location"])
        self.assertEqual(37.5796, request.latitude)
        self.assertEqual(126.977, request.longitude)
        self.assertTrue(use_congestion)

    async def test_broad_query_skips_mcp_without_congestion_preference(self):
        pipeline = RecordingPipeline()
        agent = AttractionAgent(pipeline=pipeline)

        await agent.execute(_response(
            question="서울 관광지 추천해줘",
            location="서울",
        ))

        request, use_congestion = pipeline.requests[0]
        self.assertIsNone(request.latitude)
        self.assertFalse(use_congestion)

    async def test_broad_quiet_query_uses_candidate_congestion(self):
        pipeline = RecordingPipeline()
        agent = AttractionAgent(pipeline=pipeline)

        await agent.execute(_response(
            question="오늘 고즈넉한 서울 관광지 추천해줘",
            location="서울",
        ))

        request, use_congestion = pipeline.requests[0]
        self.assertIsNone(request.latitude)
        self.assertTrue(use_congestion)

    async def test_rejects_non_ready_response(self):
        agent = AttractionAgent(pipeline=RecordingPipeline())

        with self.assertRaisesRegex(ValueError, "ready"):
            await agent.execute(_response(status="collecting"))


if __name__ == "__main__":
    unittest.main()
