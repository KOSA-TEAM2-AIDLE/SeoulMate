import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from routers.chat import _empty_restaurant_message, _restaurant_stream, _stream
from schemas.chat import ChatRequest
from schemas.structured_query import StructuredTravelQuery
from services.intent import classify_intent
from services.source_router import SourceDecision, mode_to_intent, normalize_source_mode
from services.weather_mcp_client import get_weather_via_mcp


class SourceRouterTests(unittest.TestCase):
    def test_specific_menu_empty_result_explains_verified_menu_gap(self):
        message = _empty_restaurant_message({
            "menu_no_match": True,
            "required_menu_terms": ["마라탕"],
            "location_name": "홍대입구역",
        }, "ko")
        self.assertIn("마라탕 메뉴가 확인된 식당", message)
        self.assertIn("검색 반경", message)

    def test_three_source_modes_map_to_existing_contract(self):
        self.assertEqual(mode_to_intent("RAG_ONLY"), "rag")
        self.assertEqual(mode_to_intent("RAG_MCP"), "both")
        self.assertEqual(mode_to_intent("MCP_ONLY"), "mcp")
        self.assertEqual(mode_to_intent("rag_only"), "rag")
        self.assertEqual(mode_to_intent("rag_mcp"), "both")
        self.assertEqual(mode_to_intent("mcp_only"), "mcp")
        self.assertEqual(normalize_source_mode("RAG_MCP"), "rag_mcp")

    def test_source_decision_schema_rejects_unknown_mode(self):
        decision = SourceDecision(mode="RAG_MCP", reason="방문 시각이 포함된 추천")
        self.assertEqual(decision.mode, "RAG_MCP")
        with self.assertRaises(ValueError):
            SourceDecision(mode="UNKNOWN", reason="invalid")

    def test_accommodation_and_tonight_are_not_multi_day_routes(self):
        self.assertNotEqual(classify_intent("숙박 추천", "ko", []), "route_multi")
        self.assertNotEqual(classify_intent("weather tonight", "en", []), "route_multi")
        self.assertEqual(classify_intent("2박 3일 여행", "ko", []), "route_multi")
        self.assertEqual(classify_intent("a 2 nights travel plan", "en", []), "route_multi")

    def test_mcp_bridge_fails_softly(self):
        with patch(
            "services.weather_mcp_client.streamable_http_client",
            side_effect=RuntimeError("offline"),
        ):
            result = asyncio.run(
                get_weather_via_mcp("내일 날씨", 37.5665, 126.9780, "ko")
            )
        self.assertFalse(result["available"])
        self.assertEqual(result["source"], "weather-mcp-unavailable")
        self.assertFalse(result["should_affect_recommendation"])


async def _fake_recommendation_stream(*args, **kwargs):
    yield "테스트 답변"


def _fake_recommendation_result(*args, **kwargs):
    candidates = args[2]
    return {
        "answer": "테스트 답변",
        "selections": [
            {"candidate": candidate, "selection_reason": "테스트 선정 이유"}
            for candidate in candidates[:3]
        ],
    }


async def _fake_restaurant_stream(*args, **kwargs):
    yield "data: {}\n\n"


class RestaurantSourceModeTests(unittest.IsolatedAsyncioTestCase):
    def _rag_result(self):
        return {
            "candidates": [
                {
                    "restaurant_id": 1,
                    "name": "테스트 식당",
                    "category": "한식",
                    "score": 0.9,
                    "evidence": {"menus": [], "reviews": []},
                }
            ],
            "origin_lat": 37.5665,
            "origin_lng": 126.9780,
        }

    async def test_rag_only_skips_mcp_and_weather_reranking(self):
        body = ChatRequest(message="조용한 식당 추천", lang="ko")
        with (
            patch("routers.chat.search_restaurants", return_value=self._rag_result()),
            patch("routers.chat.get_weather_via_mcp", new_callable=AsyncMock) as weather_mcp,
            patch("routers.chat.rerank_with_weather") as weather_reranker,
            patch("routers.chat.generate_recommendation_result", _fake_recommendation_result),
        ):
            events = [event async for event in _restaurant_stream(body, "RAG_ONLY", "RAG만 필요")]

        weather_mcp.assert_not_awaited()
        weather_reranker.assert_not_called()
        meta = json.loads(events[0].removeprefix("data: "))
        self.assertEqual(meta["intent"], "rag")
        self.assertEqual(meta["tool_results"], [])
        self.assertNotIn("KMA-via-Weather-MCP", meta["sources"])
        self.assertIsNone(meta["places"][0]["weather_score"])

    async def test_fixed_parser_source_mode_skips_second_router_gpt(self):
        body = ChatRequest(
            message="조용한 식당 추천",
            lang="ko",
            source_mode="rag_only",
            parsed_intent="single_place_recommendation",
        )
        with (
            patch("routers.chat.classify_intent") as legacy_intent,
            patch("routers.chat.decide_source_mode", new_callable=AsyncMock) as router_gpt,
            patch("routers.chat._restaurant_stream", _fake_restaurant_stream),
        ):
            events = [event async for event in _stream(body)]

        router_gpt.assert_not_awaited()
        legacy_intent.assert_not_called()
        self.assertEqual(events, ["data: {}\n\n"])

    async def test_full_fixed_json_skips_all_legacy_parsing(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "single_place_recommendation",
            "original_question": "내일 조용한 중식당 추천",
            "normalized_question": "내일 조용한 중식당 추천",
            "tasks": [{
                "task_id": "1",
                "domain": "restaurant",
                "search_query": "조용한 중식당",
                "themes": [],
                "desired_count": 1,
            }],
            "filters": {"location": "홍대", "start_date": "2026-07-15"},
        })
        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
        with (
            patch("routers.chat.classify_intent") as legacy_intent,
            patch("routers.chat.decide_source_mode", new_callable=AsyncMock) as router_gpt,
            patch("routers.chat._restaurant_stream", _fake_restaurant_stream),
        ):
            events = [event async for event in _stream(body)]

        legacy_intent.assert_not_called()
        router_gpt.assert_not_awaited()
        self.assertEqual(events, ["data: {}\n\n"])

    async def test_rag_mcp_calls_weather_and_weather_reranking(self):
        body = ChatRequest(message="내일 저녁 식당 추천", lang="ko")
        rag_result = self._rag_result()
        weather = {"available": True, "condition": "clear", "temperature_c": 22.0}
        with (
            patch("routers.chat.search_restaurants", return_value=rag_result),
            patch(
                "routers.chat.get_weather_via_mcp",
                new_callable=AsyncMock,
                return_value=weather,
            ) as weather_mcp,
            patch(
                "routers.chat.rerank_with_weather",
                return_value=rag_result["candidates"],
            ) as weather_reranker,
            patch("routers.chat.generate_recommendation_result", _fake_recommendation_result),
        ):
            events = [event async for event in _restaurant_stream(body, "RAG_MCP", "날씨 필요")]

        weather_mcp.assert_awaited_once()
        weather_reranker.assert_called_once()
        self.assertEqual(weather_reranker.call_args.kwargs["source_mode"], "rag_mcp")
        meta = json.loads(events[0].removeprefix("data: "))
        self.assertEqual(meta["intent"], "both")
        self.assertIn("KMA-via-Weather-MCP", meta["sources"])

    async def test_structured_task_sends_top_ten_and_returns_three(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "single_place_recommendation",
            "original_question": "식당 한 곳 추천",
            "normalized_question": "식당 한 곳 추천",
            "tasks": [{
                "task_id": "1", "domain": "restaurant",
                "search_query": "식당", "desired_count": 1,
            }],
            "filters": {"location": "홍대"},
        })
        candidates = []
        for restaurant_id in range(1, 13):
            candidates.append({
                "restaurant_id": restaurant_id,
                "name": f"식당 {restaurant_id}",
                "category": "한식",
                "score": 1.0 / restaurant_id,
                "evidence": {"menus": [], "reviews": []},
            })
        captured = {}

        def capture_result(*args, **kwargs):
            captured["candidates"] = args[2]
            captured["structured_context"] = args[5]
            return _fake_recommendation_result(*args, **kwargs)

        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
        with (
            patch(
                "routers.chat.search_restaurants_structured",
                return_value={"candidates": candidates},
            ),
            patch("routers.chat.generate_recommendation_result", new=capture_result),
        ):
            events = [event async for event in _restaurant_stream(
                body, "rag_only", "structured", structured_task=parsed.tasks[0]
            )]

        self.assertEqual(len(captured["candidates"]), 10)
        self.assertEqual(captured["structured_context"]["task"]["desired_count"], 3)
        meta = json.loads(events[0].removeprefix("data: "))
        self.assertEqual(len(meta["places"]), 3)
        self.assertEqual(meta["places"][0]["restaurant_id"], "1")
        self.assertEqual(meta["places"][0]["selection_reason"], "테스트 선정 이유")
        self.assertEqual(meta["result"]["responseType"], "recommendation")
        self.assertIsNone(meta["result"]["travelPath"])
        self.assertEqual(len(meta["result"]["recommendList"]), 3)
        self.assertEqual(meta["result"]["recommendList"][0]["id"], "1")
        self.assertEqual(
            meta["result"]["recommendList"][0]["selectionReason"],
            "테스트 선정 이유",
        )

    async def test_general_response_uses_structured_language_and_instruction(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "general_response",
            "original_question": "리스트와 튜플 차이",
            "normalized_question": "리스트와 튜플의 차이 설명",
            "tasks": [],
            "filters": {},
            "general_response_instruction": "초보자에게 간단히 설명한다.",
        })
        captured = {}

        async def capture_chat(message, lang, history, response_instruction=None):
            captured.update({
                "message": message,
                "lang": lang,
                "instruction": response_instruction,
            })
            yield "일반 답변"

        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
        with patch("routers.chat.stream_chat_response", new=capture_chat):
            [event async for event in _stream(body)]

        self.assertEqual(captured["lang"], "ko")
        self.assertEqual(captured["instruction"], "초보자에게 간단히 설명한다.")


if __name__ == "__main__":
    unittest.main()
