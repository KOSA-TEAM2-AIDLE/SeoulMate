import unittest

from routers.chat import resolve_travel_query
from schemas.chat import ChatRequest
from schemas.travel_query_api import TravelQueryApiResponse


def _ready_response():
    return TravelQueryApiResponse.model_validate({
        "thread_id": "thread-ready",
        "status": "ready",
        "structured_query": {
            "language": "ko",
            "intent": "single_place_recommendation",
            "original_question": "전시 추천",
            "normalized_question": "서울 전시 추천",
            "tasks": [{
                "task_id": "attraction-1",
                "domain": "attraction",
                "search_query": "서울 전시 추천",
                "themes": ["전시"],
            }],
            "filters": {"location": "서울"},
        },
    })


class _FakeTravelQueryService:
    def __init__(self, response):
        self.response = response
        self.started = []
        self.resumed = []

    async def start(self, request):
        self.started.append(request)
        return self.response

    async def resume(self, thread_id, answer):
        self.resumed.append((thread_id, answer))
        return self.response


class ChatTravelQueryBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_raw_chat_message_starts_structuring_and_attaches_ready_query(self):
        service = _FakeTravelQueryService(_ready_response())
        body = ChatRequest(message="전시 추천", lang="ko", lat=37.56, lng=126.98)

        resolved, response = await resolve_travel_query(body, service=service)

        self.assertIsNone(response)
        self.assertEqual("attraction", resolved.parsed_query.tasks[0].domain)
        self.assertEqual("ko", service.started[0].language)
        self.assertEqual(37.56, service.started[0].lat)

    async def test_collecting_response_is_returned_without_starting_new_thread(self):
        collecting = TravelQueryApiResponse(
            thread_id="thread-collecting",
            status="collecting",
            assistant_message="어느 날짜에 방문하시나요?",
            missing_fields=["date"],
        )
        service = _FakeTravelQueryService(collecting)
        body = ChatRequest(message="이번 토요일", lang="ko", travel_query_thread_id="thread-collecting")

        resolved, response = await resolve_travel_query(body, service=service)

        self.assertIsNone(resolved)
        self.assertEqual("collecting", response.status)
        self.assertEqual([("thread-collecting", "이번 토요일")], service.resumed)
        self.assertEqual([], service.started)
