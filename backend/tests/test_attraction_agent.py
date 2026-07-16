import unittest

from domains.attraction.agent import AttractionAgent
from domains.attraction.answer_models import AttractionAnswerResult
from schemas.travel_query_api import TravelQueryApiResponse


def _response(*, status: str = "ready") -> TravelQueryApiResponse:
    values = {
        "thread_id": "attraction-agent-thread",
        "status": status,
    }
    if status == "ready":
        values["structured_query"] = {
            "language": "ko",
            "intent": "day_trip_route",
            "original_question": "경복궁 근처 관광지와 식당을 추천해줘",
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
                "location": "경복궁",
                "radius_km": 2.5,
                "start_date": "2026-07-16",
            },
        }
    else:
        values.update({
            "assistant_message": "어느 지역에서 찾을까요?",
            "missing_fields": ["filters.location"],
        })
    return TravelQueryApiResponse.model_validate(values)


class RecordingPipeline:
    def __init__(self) -> None:
        self.requests = []

    async def recommend(self, request):
        self.requests.append(request)
        return AttractionAnswerResult(
            answer="경복궁 근처 관광지 세 곳을 추천합니다.",
            selections=[],
        )


class AttractionAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_executes_only_attraction_tasks_with_structured_filters(self):
        pipeline = RecordingPipeline()
        agent = AttractionAgent(pipeline=pipeline)

        result = await agent.execute(_response())

        self.assertEqual("attraction", result.domain)
        self.assertEqual(["task_1"], result.task_ids)
        self.assertEqual(
            "경복궁 근처 관광지 세 곳을 추천합니다.",
            result.assistant_message,
        )
        self.assertEqual(1, len(pipeline.requests))
        request = pipeline.requests[0]
        self.assertEqual("task_1", request.task_id)
        self.assertEqual("attraction", request.domain)
        self.assertEqual("ko", request.language)
        self.assertEqual("경복궁 근처 역사 관광지", request.search_query)
        self.assertEqual(["역사", "문화"], request.themes)
        self.assertEqual("경복궁", request.location)
        self.assertEqual(2.5, request.radius_km)
        self.assertEqual("2026-07-16", request.visit_date.isoformat())

    async def test_rejects_non_ready_response(self):
        agent = AttractionAgent(pipeline=RecordingPipeline())

        with self.assertRaisesRegex(ValueError, "ready"):
            await agent.execute(_response(status="collecting"))


if __name__ == "__main__":
    unittest.main()
