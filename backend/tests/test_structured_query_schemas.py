import unittest

from pydantic import ValidationError

from application.travel_query.checkpoint import (
    create_development_checkpointer,
)
from schemas.chat import ChatRequest
from schemas.hitl import HumanInTheLoopResponse
from schemas.structured_query import StructuredTravelQuery


def _single_place_payload() -> dict:
    return {
        "language": "ko",
        "intent": "single_place_recommendation",
        "original_question": "홍대에서 조용한 카페 추천해줘",
        "normalized_question": "홍대 조용한 카페 추천",
        "tasks": [
            {
                "task_id": "task_1",
                "domain": "cafe",
                "search_query": "홍대 조용한 카페",
                "themes": ["조용한"],
                "desired_count": 3,
            }
        ],
        "filters": {
            "location": "홍대",
            "is_active": True,
        },
    }


def _day_route_payload() -> dict:
    return {
        "language": "ko",
        "intent": "day_trip_route",
        "original_question": "내일 홍대에서 저녁 먹고 카페도 가고 싶어",
        "normalized_question": "2026-07-16 홍대 저녁 식사 후 카페 방문",
        "tasks": [
            {
                "task_id": "task_1",
                "domain": "restaurant",
                "search_query": "홍대 저녁 식사",
                "desired_count": 1,
                "slot_id": "d1-restaurant-1",
                "day_number": 1,
                "visit_date": "2026-07-16",
                "start_time": "19:00",
                "end_time": "20:30",
            },
            {
                "task_id": "task_2",
                "domain": "cafe",
                "search_query": "홍대 분위기 좋은 카페",
                "desired_count": 1,
                "slot_id": "d1-cafe-1",
                "day_number": 1,
                "visit_date": "2026-07-16",
                "start_time": "21:00",
                "end_time": "22:00",
            },
        ],
        "filters": {
            "location": "홍대",
            "start_date": "2026-07-16",
            "end_date": "2026-07-16",
            "is_active": True,
        },
        "route_request": {
            "destination": "홍대",
            "period": {
                "start_date": "2026-07-16",
                "end_date": "2026-07-16",
                "nights": 0,
                "days": 1,
            },
            "pace": "normal",
            "max_places_per_day": 5,
            "target_places_per_day": 2,
            "preferred_areas": ["홍대"],
            "preferred_themes": ["분위기 좋은"],
        },
        "weather_request": {
            "query": "내일 홍대에서 저녁을 먹고 분위기 좋은 카페도 가고 싶어",
            "location_name": "홍대",
            "target_date": "2026-07-16",
            "target_time": "19:00",
            "language": "ko",
        },
    }


def _multi_day_payload() -> dict:
    return {
        "language": "ko",
        "intent": "multi_day_route",
        "original_question": "서울 1박 2일 여행을 계획해줘",
        "normalized_question": "2026-08-01부터 서울 1박 2일 여행",
        "tasks": [
            {
                "task_id": "task_1",
                "domain": "attraction",
                "search_query": "홍대 전시",
                "desired_count": 1,
                "slot_id": "d1-attraction-1",
                "day_number": 1,
                "visit_date": "2026-08-01",
            },
            {
                "task_id": "task_2",
                "domain": "cafe",
                "search_query": "성수 카페",
                "desired_count": 1,
                "slot_id": "d2-cafe-1",
                "day_number": 2,
                "visit_date": "2026-08-02",
            },
        ],
        "filters": {
            "location": "서울",
            "start_date": "2026-08-01",
            "end_date": "2026-08-02",
        },
        "route_request": {
            "destination": "서울",
            "period": {
                "start_date": "2026-08-01",
                "end_date": "2026-08-02",
                "nights": 1,
                "days": 2,
            },
            "adults": 2,
            "children": 0,
            "arrival_at": "10:00",
            "arrival_location": "서울역",
            "departure_at": "20:00",
            "departure_location": "서울역",
            "pace": "normal",
            "max_places_per_day": 5,
            "target_places_per_day": None,
            "transportation": ["지하철"],
            "preferred_areas": ["홍대", "성수"],
            "preferred_themes": ["맛집", "전시"],
            "required_features": [],
            "excluded_features": [],
            "must_visit": [],
            "avoid_places": [],
        },
    }


class StructuredTravelQuerySchemaTests(unittest.TestCase):
    def test_single_place_contract_is_valid(self) -> None:
        query = StructuredTravelQuery.model_validate(_single_place_payload())

        self.assertEqual("single_place_recommendation", query.intent)
        self.assertEqual(3, query.tasks[0].desired_count)
        self.assertTrue(query.filters.is_active)

    def test_single_place_count_is_corrected_to_three(self) -> None:
        payload = _single_place_payload()
        payload["tasks"][0]["desired_count"] = 1

        query = StructuredTravelQuery.model_validate(payload)

        self.assertEqual(3, query.tasks[0].desired_count)

    def test_day_route_task_count_must_match_target(self) -> None:
        payload = _day_route_payload()
        payload["route_request"]["target_places_per_day"] = 3

        with self.assertRaisesRegex(ValidationError, "Task 수와"):
            StructuredTravelQuery.model_validate(payload)

    def test_json_dump_normalizes_dates_and_times(self) -> None:
        query = StructuredTravelQuery.model_validate(_day_route_payload())
        payload = query.model_dump(mode="json")

        self.assertEqual("2026-07-16", payload["tasks"][0]["visit_date"])
        self.assertEqual("19:00", payload["tasks"][0]["start_time"])

    def test_route_metadata_is_optional_but_validated_when_present(self) -> None:
        payload = _day_route_payload()
        for task in payload["tasks"]:
            task.pop("slot_id")
            task.pop("day_number")
            task.pop("visit_date")

        query = StructuredTravelQuery.model_validate(payload)

        self.assertIsNone(query.tasks[0].slot_id)

    def test_day_route_must_have_one_day_period(self) -> None:
        payload = _day_route_payload()
        payload["route_request"]["period"] = {
            "start_date": "2026-07-16",
            "end_date": "2026-07-17",
            "nights": 1,
            "days": 2,
        }

        with self.assertRaisesRegex(ValidationError, "1일"):
            StructuredTravelQuery.model_validate(payload)

    def test_multi_day_contract_does_not_match_total_tasks_to_target(self) -> None:
        query = StructuredTravelQuery.model_validate(_multi_day_payload())
        payload = query.model_dump(mode="json")

        self.assertIsNone(query.route_request.target_places_per_day)
        self.assertEqual("10:00", payload["route_request"]["arrival_at"])
        self.assertEqual(2, len(query.tasks))

    def test_general_response_requires_instruction(self) -> None:
        payload = {
            "language": "ko",
            "intent": "general_response",
            "original_question": "안녕",
            "normalized_question": "인사",
            "tasks": [],
            "filters": {},
        }

        with self.assertRaisesRegex(ValidationError, "instruction"):
            StructuredTravelQuery.model_validate(payload)


class ChatRequestContractTests(unittest.TestCase):
    def test_final_query_is_sent_as_parsed_query(self) -> None:
        request = ChatRequest.model_validate(
            {
                "message": "내일 홍대에서 저녁 먹고 카페도 가고 싶어",
                "lang": "ko",
                "lat": 37.5563,
                "lng": 126.9236,
                "location_name": "홍대",
                "parsed_intent": "day_trip_route",
                "source_mode": None,
                "parsed_query": _day_route_payload(),
                "route_modification": None,
            }
        )

        self.assertEqual(request.parsed_intent, request.parsed_query.intent)

    def test_parsed_intent_must_match_query_intent(self) -> None:
        with self.assertRaisesRegex(ValidationError, "parsed_intent"):
            ChatRequest.model_validate(
                {
                    "message": "홍대 카페 추천",
                    "parsed_intent": "general_response",
                    "parsed_query": _single_place_payload(),
                }
            )

    def test_route_modification_is_separate_from_gpt_query(self) -> None:
        parsed_query = {
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
        }

        request = ChatRequest.model_validate(
            {
                "message": "첫날 카페를 다른 곳으로 바꿔줘",
                "parsed_intent": "modify_route",
                "parsed_query": parsed_query,
                "route_modification": {
                    "current_route": {"route_id": "route_1"},
                    "target_slot_id": "d1-cafe-1",
                    "expected_version": 3,
                },
            }
        )

        self.assertNotIn(
            "current_route",
            request.parsed_query.model_dump(mode="json"),
        )
        self.assertEqual(
            "d1-cafe-1",
            request.route_modification.target_slot_id,
        )


class HumanInTheLoopSchemaTests(unittest.TestCase):
    def test_collecting_state_requires_question(self) -> None:
        state = HumanInTheLoopResponse(
            status="collecting",
            assistant_message="하루에 몇 곳 정도 방문하고 싶으세요?",
            missing_fields=["route_request.target_places_per_day"],
            collected={"location": "홍대"},
        )

        self.assertIsNone(state.structured_query)

    def test_ready_state_contains_only_structured_query(self) -> None:
        query = StructuredTravelQuery.model_validate(_single_place_payload())
        state = HumanInTheLoopResponse(
            status="ready",
            structured_query=query,
        )

        self.assertEqual(query, state.structured_query)

    def test_unsupported_state_returns_fixed_message(self) -> None:
        state = HumanInTheLoopResponse(
            status="unsupported",
            assistant_message="루트 수정은 지원하지 않습니다.",
        )

        self.assertIsNone(state.structured_query)
        self.assertEqual([], state.missing_fields)

    def test_development_checkpointer_can_be_created(self) -> None:
        self.assertIsNotNone(create_development_checkpointer())


if __name__ == "__main__":
    unittest.main()
