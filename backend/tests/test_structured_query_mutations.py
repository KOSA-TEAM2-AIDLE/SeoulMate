"""첫 GPT JSON이 누락·충돌·환각 값을 포함할 때의 계약 회귀 테스트."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from schemas.chat import ChatRequest
from schemas.structured_query import StructuredTravelQuery


def single_query(**updates) -> dict:
    payload = {
        "language": "ko",
        "intent": "single_place_recommendation",
        "original_question": "홍대에서 조용한 카페 추천해줘",
        "normalized_question": "홍대 조용한 카페 추천",
        "source_mode": "rag_only",
        "tasks": [{
            "task_id": "task_1",
            "domain": "cafe",
            "search_query": "홍대 조용한 카페",
            "themes": ["조용한"],
            "desired_count": 1,
        }],
        "filters": {"location": "홍대"},
    }
    payload.update(updates)
    return payload


def day_route(**updates) -> dict:
    payload = {
        "language": "ko",
        "intent": "day_trip_route",
        "original_question": "내일 홍대 당일 루트 짜줘",
        "normalized_question": "홍대 당일 루트",
        "source_mode": "rag_mcp",
        "tasks": [
            {
                "task_id": "task_1",
                "domain": "restaurant",
                "search_query": "홍대 점심 식당",
                "slot_id": "d1-restaurant-1",
                "day_number": 1,
                "visit_date": "2026-07-16",
                "start_time": "12:00",
                "end_time": "13:00",
                "desired_count": 3,
            },
            {
                "task_id": "task_2",
                "domain": "cafe",
                "search_query": "홍대 카페",
                "slot_id": "d1-cafe-1",
                "day_number": 1,
                "visit_date": "2026-07-16",
                "start_time": "14:00",
                "end_time": "15:00",
            },
        ],
        "filters": {
            "location": "홍대",
            "start_date": "2026-07-16",
            "end_date": "2026-07-16",
        },
        "route_request": {
            "destination": "홍대",
            "period": {
                "start_date": "2026-07-16",
                "end_date": "2026-07-16",
                "nights": 0,
                "days": 1,
            },
            "max_places_per_day": 5,
            "target_places_per_day": 2,
        },
    }
    payload.update(updates)
    return payload


class StructuredQueryMutationTests(unittest.TestCase):
    def test_single_choice_count_is_server_normalized_to_three(self):
        parsed = StructuredTravelQuery.model_validate(single_query())
        self.assertEqual(parsed.tasks[0].desired_count, 3)

    def test_null_filters_are_normalized(self):
        parsed = StructuredTravelQuery.model_validate(single_query(filters=None))
        self.assertEqual(parsed.filters.required_features, [])

    def test_legacy_route_context_is_ignored(self):
        parsed = StructuredTravelQuery.model_validate(single_query(
            route_context={"operation": "replace", "target_slot_id": "old"},
        ))
        self.assertFalse(hasattr(parsed, "route_context"))

    def test_weather_task_is_removed_when_a_place_task_exists(self):
        payload = single_query()
        payload["tasks"].append({
            "task_id": "weather_1",
            "domain": "weather",
            "search_query": "내일 날씨",
        })
        parsed = StructuredTravelQuery.model_validate(payload)
        self.assertEqual([task.domain for task in parsed.tasks], ["cafe"])

    def test_unknown_intent_is_rejected(self):
        with self.assertRaises(ValidationError):
            StructuredTravelQuery.model_validate(single_query(intent="route_edit"))

    def test_unknown_domain_is_rejected(self):
        payload = single_query()
        payload["tasks"][0]["domain"] = "museum"
        with self.assertRaises(ValidationError):
            StructuredTravelQuery.model_validate(payload)

    def test_duplicate_task_ids_are_rejected(self):
        payload = single_query()
        payload["tasks"].append({
            "task_id": "task_1",
            "domain": "restaurant",
            "search_query": "홍대 식당",
        })
        with self.assertRaisesRegex(ValidationError, "task_id"):
            StructuredTravelQuery.model_validate(payload)

    def test_more_than_five_general_recommendation_tasks_are_rejected(self):
        payload = single_query(tasks=[
            {
                "task_id": f"task_{index}",
                "domain": "cafe",
                "search_query": f"카페 {index}",
            }
            for index in range(6)
        ])
        with self.assertRaisesRegex(ValidationError, "최대 5개"):
            StructuredTravelQuery.model_validate(payload)

    def test_single_recommendation_without_place_task_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "장소 Task"):
            StructuredTravelQuery.model_validate(single_query(tasks=[]))

    def test_weather_intent_rejects_place_tasks(self):
        with self.assertRaisesRegex(ValidationError, "장소 Task"):
            StructuredTravelQuery.model_validate(single_query(
                intent="weather_information",
                source_mode="mcp_only",
            ))

    def test_general_intent_rejects_source_mode(self):
        with self.assertRaisesRegex(ValidationError, "source_mode"):
            StructuredTravelQuery.model_validate(single_query(
                intent="general_response",
                tasks=[],
            ))

    def test_place_intent_rejects_mcp_only(self):
        with self.assertRaisesRegex(ValidationError, "mcp_only"):
            StructuredTravelQuery.model_validate(single_query(source_mode="mcp_only"))

    def test_clock_time_is_normalized(self):
        payload = day_route()
        payload["tasks"][0]["start_time"] = "9:05"
        parsed = StructuredTravelQuery.model_validate(payload)
        self.assertEqual(parsed.tasks[0].start_time, "09:05")

    def test_invalid_clock_time_is_rejected_early(self):
        payload = day_route()
        payload["tasks"][0]["start_time"] = "25:99"
        with self.assertRaisesRegex(ValidationError, "시간"):
            StructuredTravelQuery.model_validate(payload)

    def test_reversed_same_day_interval_is_rejected(self):
        payload = day_route()
        payload["tasks"][0]["end_time"] = "11:00"
        with self.assertRaisesRegex(ValidationError, "end_time"):
            StructuredTravelQuery.model_validate(payload)

    def test_day_route_rejects_multi_day_period(self):
        payload = day_route()
        payload["route_request"]["period"] = {
            "start_date": "2026-07-16",
            "end_date": "2026-07-17",
            "nights": 1,
            "days": 2,
        }
        with self.assertRaisesRegex(ValidationError, "1일"):
            StructuredTravelQuery.model_validate(payload)

    def test_task_day_outside_period_is_rejected_not_clamped(self):
        payload = day_route()
        payload["tasks"][0]["day_number"] = 5
        with self.assertRaisesRegex(ValidationError, "day_number"):
            StructuredTravelQuery.model_validate(payload)

    def test_task_date_outside_period_is_rejected(self):
        payload = day_route()
        payload["tasks"][0].pop("day_number")
        payload["tasks"][0]["visit_date"] = "2026-07-20"
        with self.assertRaisesRegex(ValidationError, "visit_date"):
            StructuredTravelQuery.model_validate(payload)

    def test_duplicate_route_slot_ids_are_rejected(self):
        payload = day_route()
        payload["tasks"][1]["slot_id"] = payload["tasks"][0]["slot_id"]
        with self.assertRaisesRegex(ValidationError, "slot_id"):
            StructuredTravelQuery.model_validate(payload)

    def test_route_desired_count_is_normalized_to_one(self):
        parsed = StructuredTravelQuery.model_validate(day_route())
        self.assertTrue(all(task.desired_count == 1 for task in parsed.tasks))

    def test_multi_day_route_rejects_empty_day(self):
        payload = day_route(
            intent="multi_day_route",
            original_question="1박 2일 서울 여행",
        )
        payload["route_request"]["period"] = {
            "start_date": "2026-07-16",
            "end_date": "2026-07-17",
            "nights": 1,
            "days": 2,
        }
        payload["route_request"]["target_places_per_day"] = None
        with self.assertRaisesRegex(ValidationError, "누락 Day"):
            StructuredTravelQuery.model_validate(payload)

    def test_daily_task_count_cannot_exceed_route_limit(self):
        payload = day_route()
        payload["route_request"]["max_places_per_day"] = 1
        payload["route_request"]["target_places_per_day"] = 1
        with self.assertRaisesRegex(ValidationError, "max_places_per_day"):
            StructuredTravelQuery.model_validate(payload)

    def test_chat_rejects_conflicting_parsed_intent(self):
        parsed = StructuredTravelQuery.model_validate(single_query())
        with self.assertRaisesRegex(ValidationError, "parsed_intent"):
            ChatRequest(
                message=parsed.original_question,
                parsed_intent="day_trip_route",
                parsed_query=parsed,
            )

    def test_chat_rejects_conflicting_source_mode(self):
        parsed = StructuredTravelQuery.model_validate(single_query())
        with self.assertRaisesRegex(ValidationError, "source_mode"):
            ChatRequest(
                message=parsed.original_question,
                source_mode="rag_mcp",
                parsed_query=parsed,
            )

    def test_chat_accepts_matching_structured_contract(self):
        parsed = StructuredTravelQuery.model_validate(single_query())
        request = ChatRequest(
            message=parsed.original_question,
            parsed_intent=parsed.intent,
            source_mode=parsed.source_mode,
            parsed_query=parsed,
        )
        self.assertEqual(request.parsed_query.intent, "single_place_recommendation")


if __name__ == "__main__":
    unittest.main()
