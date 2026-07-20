import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from routers.chat import (
    _prefetch_route_weather,
    _route_candidate_window,
    _route_slot_start_time,
    _route_slot_start_times,
    _stream,
)
from schemas.chat import ChatRequest
from schemas.structured_query import StructuredTravelQuery
from services.domain_agents import mock_places_for_task
from services.route_planner import validate_route_planner_output


def query_with_tasks(*, intent="single_place_recommendation", start_date=None, tasks=None):
    return StructuredTravelQuery.model_validate({
        "language": "ko",
        "intent": intent,
        "original_question": "내일 홍대에서 저녁을 먹고 분위기 좋은 카페도 가고 싶어",
        "normalized_question": "홍대 식당과 카페",
        "tasks": tasks or [],
        "filters": {"location": "홍대", "start_date": start_date, "end_date": start_date},
    })


def restaurant_task():
    return {
        "task_id": "1",
        "domain": "restaurant",
        "search_query": "홍대 저녁 식사",
        "themes": ["저녁"],
        "desired_count": 1,
    }


def cafe_task():
    return {
        "task_id": "2",
        "domain": "cafe",
        "search_query": "홍대 분위기 좋은 카페",
        "themes": ["분위기 좋은"],
        "desired_count": 1,
    }


def restaurant_result():
    return {
        "candidates": [{
            "restaurant_id": 10,
            "name": "실제 식당 후보",
            "category": "한국",
            "score": 0.9,
            "rag_score": 0.9,
            "weather_score": None,
            "weather_reasons": [],
            "evidence": {"menus": [], "reviews": []},
        }],
        "origin_lat": 37.5563,
        "origin_lng": 126.9236,
    }


def decode_sse(event: str) -> dict:
    return json.loads(event.removeprefix("data: "))


def fake_grouped_result(*args, **kwargs):
    groups = args[2]
    return {
        "answer": "도메인별 추천 결과",
        "task_results": [
            {
                "task_id": str(group["task_id"]),
                "domain": group["domain"],
                "selections": [
                    {"candidate": candidate, "selection_reason": "그룹별 선정 이유"}
                    for candidate in group["candidates"][:3]
                ],
            }
            for group in groups
        ],
    }


def fake_route_plan(planner_input):
    return validate_route_planner_output(json.dumps({
        "title": "검증된 추천 루트",
        "summary": "동선을 고려한 일정입니다.",
        "selections": [
            {
                "slot_id": slot.slot_id,
                "selected_candidate_id": slot.candidates[0].candidate_id,
                "selection_reason": "대표 장소로 가장 적합합니다.",
                "alternatives": [
                    {
                        "candidate_id": candidate.candidate_id,
                        "selection_reason": f"대안 {index}입니다.",
                    }
                    for index, candidate in enumerate(slot.candidates[1:3], start=1)
                ],
            }
            for slot in planner_input.slots
        ],
    }, ensure_ascii=False), planner_input)


class MockDomainAgentTests(unittest.IsolatedAsyncioTestCase):
    def test_accommodation_mock_candidates_are_available(self):
        parsed = query_with_tasks(tasks=[{
            "task_id": "hotel-1",
            "domain": "accommodation",
            "search_query": "서울 숙소",
            "desired_count": 3,
        }])

        places = mock_places_for_task(parsed.tasks[0], candidate_count=7)

        self.assertEqual(len(places), 7)
        self.assertTrue(all(place.source_type == "accommodation" for place in places))
        self.assertEqual(places[0].name, "임시 숙소 후보 1")

    def test_repeated_route_slots_shift_candidate_window(self):
        candidates = list(range(10))

        self.assertEqual(_route_candidate_window(candidates, 0), [0, 1, 2, 3, 4])
        self.assertEqual(_route_candidate_window(candidates, 1), [1, 2, 3, 4, 5])
        self.assertEqual(_route_candidate_window(candidates, 5), [5, 6, 7, 8, 9])

    def test_restaurant_route_time_uses_meal_keyword_when_start_time_missing(self):
        parsed = query_with_tasks(tasks=[{
            "task_id": "lunch",
            "domain": "restaurant",
            "search_query": "홍대 점심 식당",
            "themes": ["점심"],
            "desired_count": 1,
        }])

        self.assertEqual("12:00", _route_slot_start_time(parsed.tasks[0]))

    def test_cafe_default_time_follows_lunch_or_dinner_context(self):
        lunch_route = query_with_tasks(tasks=[
            restaurant_task() | {"search_query": "홍대 점심 식당", "themes": ["점심"]},
            cafe_task(),
        ])
        dinner_route = query_with_tasks(tasks=[restaurant_task(), cafe_task()])

        self.assertEqual("16:00", _route_slot_start_times(lunch_route.tasks)["2"])
        self.assertEqual("20:30", _route_slot_start_times(dinner_route.tasks)["2"])

    def test_mock_agent_returns_explicit_placeholder(self):
        parsed = query_with_tasks(tasks=[cafe_task()])
        places = mock_places_for_task(parsed.tasks[0], lat=37.5, lng=126.9)
        self.assertEqual(places[0].source_type, "cafe")
        self.assertIn("임시", places[0].name)
        self.assertIsNone(places[0].weather_score)

    def test_same_mock_place_keeps_stable_id_across_tasks(self):
        first_payload = cafe_task()
        first_payload["task_id"] = "cafe_1"
        second_payload = cafe_task()
        second_payload["task_id"] = "cafe_2"
        first = query_with_tasks(tasks=[first_payload]).tasks[0]
        second = query_with_tasks(tasks=[second_payload]).tasks[0]
        first_places = mock_places_for_task(first, candidate_count=3)
        second_places = mock_places_for_task(second, candidate_count=3)
        self.assertEqual(
            [place.source_id for place in first_places],
            [place.source_id for place in second_places],
        )
        self.assertNotEqual(first_places[0].task_id, second_places[0].task_id)

    async def test_single_cafe_uses_real_service_without_restaurant_search(self):
        parsed = query_with_tasks(tasks=[cafe_task()])
        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
        with (
            patch("domains.restaurant.search_service.search_restaurants_structured") as restaurant_search,
            patch("routers.chat.generate_grouped_recommendation_result", fake_grouped_result),
        ):
            events = [event async for event in _stream(body)]

        restaurant_search.assert_not_called()
        meta = decode_sse(events[0])
        # 원문에 '내일'이 있으므로 파서가 날짜 필드를 빠뜨려도 날씨 경로를 사용한다.
        self.assertEqual(meta["intent"], "both")
        self.assertEqual(meta["places"][0]["source_type"], "cafe")
        self.assertIn("cafe-search-service", meta["sources"])

    async def test_single_restaurant_candidate_survives_llm_failure_in_chat_api(self):
        parsed = query_with_tasks(tasks=[restaurant_task()])
        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
        with (
            patch("domains.restaurant.search_service.search_restaurants_structured", return_value=restaurant_result()),
            patch(
                "routers.chat.get_weather_via_mcp",
                new_callable=AsyncMock,
                return_value={"available": False, "error": "offline"},
            ),
            patch("services.llm._client", side_effect=RuntimeError("llm offline")),
        ):
            events = [event async for event in _stream(body)]
        meta = decode_sse(events[0])
        self.assertEqual(len(meta["places"]), 1)
        self.assertEqual(meta["places"][0]["restaurant_id"], "10")
        self.assertEqual(decode_sse(events[-1])["type"], "done")

    async def test_mixed_tasks_use_real_restaurant_and_cafe(self):
        parsed = query_with_tasks(
            start_date="2026-07-15",
            tasks=[restaurant_task(), cafe_task()],
        )
        body = ChatRequest(
            message=parsed.original_question,
            parsed_query=parsed,
            lat=37.5563,
            lng=126.9236,
            location_name="홍대",
        )
        weather = {"available": True, "condition": "clear", "temperature_c": 24.0}
        with (
            patch("domains.restaurant.search_service.search_restaurants_structured", return_value=restaurant_result()),
            patch("routers.chat.get_weather_via_mcp", new_callable=AsyncMock, return_value=weather) as mcp,
            patch("routers.chat.generate_grouped_recommendation_result", fake_grouped_result),
        ):
            events = [event async for event in _stream(body)]

        mcp.assert_awaited_once()
        meta = decode_sse(events[0])
        self.assertEqual(meta["intent"], "both")
        self.assertEqual(
            {place["source_type"] for place in meta["places"]},
            {"restaurant", "cafe"},
        )
        self.assertIn("cafe-search-service", meta["sources"])
        self.assertIn("KMA-via-Weather-MCP", meta["sources"])

    async def test_weather_geocodes_target_when_current_location_name_is_missing(self):
        parsed = query_with_tasks(
            start_date="2026-07-15",
            tasks=[restaurant_task(), cafe_task()],
        )
        body = ChatRequest(
            message=parsed.original_question,
            parsed_query=parsed,
            lat=37.5665,
            lng=126.9780,
            location_name=None,
        )
        weather = {"available": True, "condition": "clear", "temperature_c": 24.0}
        with (
            patch("domains.restaurant.search_service.search_restaurants_structured", return_value=restaurant_result()),
            patch(
                "routers.chat.geocode_kakao",
                return_value=(37.5569, 126.9238, "홍대입구역"),
            ) as geocode,
            patch(
                "routers.chat.get_weather_via_mcp",
                new_callable=AsyncMock,
                return_value=weather,
            ) as mcp,
            patch("routers.chat.generate_grouped_recommendation_result", fake_grouped_result),
        ):
            [event async for event in _stream(body)]

        geocode.assert_called_once_with("홍대")
        args = mcp.await_args.args
        self.assertAlmostEqual(args[1], 37.5569)
        self.assertAlmostEqual(args[2], 126.9238)

    async def test_multi_task_sends_ten_candidates_and_returns_three_per_group(self):
        parsed = query_with_tasks(tasks=[restaurant_task(), cafe_task()])
        restaurants = []
        for index in range(1, 13):
            restaurants.append({
                "restaurant_id": index,
                "name": f"식당 {index}",
                "category": "한국",
                "score": 1 / index,
                "evidence": {"menus": [], "reviews": []},
            })
        captured = {}

        def capture(*args, **kwargs):
            captured["groups"] = args[2]
            return fake_grouped_result(*args, **kwargs)

        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
        with (
            patch(
                "domains.restaurant.search_service.search_restaurants_structured",
                return_value={"candidates": restaurants},
            ),
            patch("routers.chat.generate_grouped_recommendation_result", capture),
        ):
            events = [event async for event in _stream(body)]

        self.assertEqual([len(group["candidates"]) for group in captured["groups"]], [10, 10])
        meta = decode_sse(events[0])
        self.assertEqual(len(meta["places"]), 6)
        self.assertEqual(
            {place["task_id"] for place in meta["places"]}, {"1", "2"}
        )
        self.assertEqual(
            [place["rank"] for place in meta["places"] if place["task_id"] == "1"],
            [1, 2, 3],
        )

    async def test_structured_mcp_only_uses_target_location_and_language(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "weather_information",
            "original_question": "내일 홍대 날씨 알려줘",
            "normalized_question": "내일 홍대 날씨",
            "tasks": [],
            "filters": {"location": "홍대"},
            "weather_request": {
                "query": "내일 홍대 날씨",
                "location_name": "홍대",
                "target_date": "2026-07-15",
                "language": "ko",
            },
        })
        body = ChatRequest(
            message=parsed.original_question,
            parsed_query=parsed,
            lat=37.5665,
            lng=126.9780,
            location_name=None,
        )

        async def fake_answer(*_args, **_kwargs):
            yield "날씨 응답"

        with (
            patch(
                "routers.chat.geocode_kakao",
                return_value=(37.5569, 126.9238, "홍대입구역"),
            ),
            patch(
                "routers.chat.get_weather_via_mcp",
                new_callable=AsyncMock,
                return_value={"available": True, "condition": "clear"},
            ) as mcp,
            patch("routers.chat.stream_mcp_only_answer", new=fake_answer),
        ):
            events = [event async for event in _stream(body)]

        args = mcp.await_args.args
        self.assertAlmostEqual(args[1], 37.5569)
        self.assertAlmostEqual(args[2], 126.9238)
        self.assertEqual(args[3], "ko")
        meta = decode_sse(events[0])
        self.assertEqual(meta["intent"], "mcp")
        self.assertTrue(meta["tool_results"][0]["ok"])

    async def test_day_route_builds_slots_with_mock_domains(self):
        parsed = query_with_tasks(
            intent="day_trip_route",
            start_date="2026-07-15",
            tasks=[restaurant_task(), cafe_task()],
        )
        body = ChatRequest(
            message=parsed.original_question,
            parsed_query=parsed,
            lat=37.5563,
            lng=126.9236,
            location_name="홍대",
        )
        with (
            patch("domains.restaurant.search_service.search_restaurants_structured", return_value=restaurant_result()),
            patch(
                "routers.chat.get_weather_via_mcp",
                new_callable=AsyncMock,
                return_value={"available": False, "error": "offline"},
            ),
            patch("routers.chat.generate_route_plan", side_effect=fake_route_plan),
        ):
            events = [event async for event in _stream(body)]

        meta = decode_sse(events[0])
        self.assertEqual(meta["intent"], "route_day")
        self.assertEqual(meta["total_places"], 2)
        self.assertEqual(len(meta["days"][0]["slots"]), 2)
        self.assertEqual(meta["result"]["responseType"], "route")
        self.assertEqual(meta["result"]["allDay"], 1)
        self.assertIsNone(meta["result"]["recommendList"])
        self.assertEqual(len(meta["result"]["travelPath"]["1"]), 2)
        self.assertEqual(len(meta["days"][0]["slots"][0]["alternatives"]), 0)
        # 임시 카페 Agent는 5개 후보이므로 대표 외 대안 2곳을 노출한다.
        self.assertEqual(len(meta["days"][0]["slots"][1]["alternatives"]), 2)

    async def test_repeated_domain_slots_keep_task_identity_and_distinct_places(self):
        tasks = [
            {
                "task_id": "morning",
                "domain": "attraction",
                "search_query": "서울 오전 명소",
                "desired_count": 1,
                "slot_id": "d1-attraction-1",
                "day_number": 1,
                "visit_date": "2026-07-15",
                "start_time": "10:00",
            },
            {
                "task_id": "afternoon",
                "domain": "attraction",
                "search_query": "서울 오후 명소",
                "desired_count": 1,
                "slot_id": "d1-attraction-2",
                "day_number": 1,
                "visit_date": "2026-07-15",
                "start_time": "15:00",
            },
        ]
        parsed = query_with_tasks(
            intent="day_trip_route",
            start_date="2026-07-15",
            tasks=tasks,
        )
        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
        with (
            patch("routers.chat.generate_route_plan", side_effect=fake_route_plan),
            patch(
                "routers.chat._search_route_accommodation",
                new_callable=AsyncMock,
                return_value=(None, []),
            ),
            patch(
                "routers.chat.get_weather_via_mcp",
                new_callable=AsyncMock,
                return_value={"available": False, "error": "offline"},
            ),
        ):
            events = [event async for event in _stream(body)]

        meta = decode_sse(events[0])
        slots = meta["days"][0]["slots"]
        self.assertEqual([slot["place"]["task_id"] for slot in slots], ["morning", "afternoon"])
        self.assertEqual(len({slot["place"]["source_id"] for slot in slots}), 2)

    async def test_multi_day_route_places_explicit_slots_on_each_day(self):
        tasks = [restaurant_task(), cafe_task()]
        tasks[0].update({"slot_id": "d1-dinner", "day_number": 1, "visit_date": "2026-07-15", "start_time": "19:00"})
        tasks[1].update({"slot_id": "d2-cafe", "day_number": 2, "visit_date": "2026-07-16", "start_time": "11:00"})
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "multi_day_route",
            "original_question": "서울 1박 2일 루트",
            "normalized_question": "서울 1박 2일 루트",
            "tasks": tasks,
            "filters": {"location": "서울", "start_date": "2026-07-15", "end_date": "2026-07-16"},
            "route_request": {
                "destination": "서울",
                "period": {"start_date": "2026-07-15", "end_date": "2026-07-16", "nights": 1, "days": 2},
                "max_places_per_day": 5
            }
        })
        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
        with (
            patch("domains.restaurant.search_service.search_restaurants_structured", return_value=restaurant_result()),
            patch("routers.chat.generate_route_plan", side_effect=fake_route_plan),
            patch(
                "routers.chat._search_route_accommodation",
                new_callable=AsyncMock,
                return_value=(None, []),
            ),
            patch(
                "routers.chat.get_weather_via_mcp",
                new_callable=AsyncMock,
                return_value={"available": False, "error": "forecast unavailable"},
            ) as weather,
        ):
            events = [event async for event in _stream(body)]
        weather.assert_awaited_once()
        self.assertEqual(weather.await_args.kwargs["target_date"], "2026-07-15")
        self.assertEqual(weather.await_args.kwargs["target_time"], "18:00")
        meta = decode_sse(events[0])
        self.assertEqual(meta["intent"], "route_multi")
        self.assertEqual([len(day["slots"]) for day in meta["days"]], [1, 1])
        self.assertEqual(meta["days"][1]["slots"][0]["time"], "11:00")
        self.assertEqual(meta["result"]["allDay"], 2)
        self.assertEqual(list(meta["result"]["travelPath"]), ["1", "2"])

    async def test_route_weather_is_deduplicated_by_day_area_and_time_bucket(self):
        raw_tasks = []
        slot_times = {}
        for day_number, visit_date in ((1, "2026-07-15"), (2, "2026-07-16")):
            for suffix, domain, start_time in (
                ("attraction-am", "attraction", "10:00"),
                ("restaurant-noon", "restaurant", "12:30"),
                ("attraction-pm", "attraction", "17:00"),
                ("restaurant-pm", "restaurant", "19:00"),
            ):
                task_id = f"d{day_number}-{suffix}"
                raw_tasks.append({
                    "task_id": task_id,
                    "slot_id": task_id,
                    "domain": domain,
                    "search_query": "홍대 여행",
                    "desired_count": 1,
                    "day_number": day_number,
                    "visit_date": visit_date,
                    "start_time": start_time,
                    "filters": {"location": "홍대"},
                })
                slot_times[task_id] = start_time
        parsed = query_with_tasks(
            intent="multi_day_route",
            start_date="2026-07-15",
            tasks=raw_tasks,
        )
        body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
        prepared = [
            (task, task.day_number, task.visit_date, 0, 5)
            for task in parsed.tasks
        ]
        active = 0
        max_active = 0
        weather_calls = []

        async def fake_weather(*args, **kwargs):
            nonlocal active, max_active
            weather_calls.append(kwargs)
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            active -= 1
            return {"available": True, "target_time": kwargs["target_time"]}

        with (
            patch("routers.chat.geocode_kakao", return_value=(37.5563, 126.9236, "홍대")),
            patch("routers.chat.get_weather_via_mcp", new=fake_weather),
        ):
            result = await _prefetch_route_weather(body, parsed, prepared, slot_times)

        self.assertEqual(len(result), 4)
        self.assertEqual(len(weather_calls), 4)
        self.assertEqual({key[1] for key in result}, {"12:00", "18:00"})
        self.assertGreater(max_active, 1)
        self.assertLessEqual(max_active, 5)


if __name__ == "__main__":
    unittest.main()
