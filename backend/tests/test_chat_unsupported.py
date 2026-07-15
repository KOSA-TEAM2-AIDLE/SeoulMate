import asyncio
import unittest

from api.routers.chat import _stream
from schemas.chat import ChatRequest


def _modify_route_request() -> ChatRequest:
    return ChatRequest.model_validate(
        {
            "message": "첫날 카페를 다른 곳으로 바꿔줘",
            "parsed_intent": "modify_route",
            "parsed_query": {
                "language": "ko",
                "intent": "modify_route",
                "original_question": "첫날 카페를 다른 곳으로 바꿔줘",
                "normalized_question": "첫날 카페 슬롯 교체",
                "tasks": [
                    {
                        "task_id": "task_1",
                        "domain": "cafe",
                        "search_query": "첫날 일정 대체 카페",
                        "desired_count": 1,
                        "slot_id": "d1-cafe-1",
                    }
                ],
                "filters": {"location": "홍대"},
            },
            "route_modification": None,
        }
    )


async def _collect_stream(request: ChatRequest) -> list[str]:
    return [chunk async for chunk in _stream(request)]


class UnsupportedRouteModificationTests(unittest.TestCase):
    def test_chat_returns_fixed_message_without_route_data(self) -> None:
        chunks = asyncio.run(_collect_stream(_modify_route_request()))
        response = "".join(chunks)

        self.assertEqual(3, len(chunks))
        self.assertIn("루트 수정은 지원하지 않습니다.", response)
        self.assertNotIn("travelPath", response)


if __name__ == "__main__":
    unittest.main()
