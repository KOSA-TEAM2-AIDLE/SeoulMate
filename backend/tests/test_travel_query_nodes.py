import asyncio
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.runnables import RunnableLambda

from models.intent.travel_query import TravelIntentExtractor
from services.location import CITYWIDE_LOCATION_NAME
from application.travel_query.required_info import (
    ROUTE_MODIFICATION_UNSUPPORTED_MESSAGE,
    check_required_information,
    find_missing_fields,
)


SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")


def _base_state() -> dict:
    return {
        "status": "collecting",
        "original_question": "내일 홍대에서 저녁 먹고 카페도 가고 싶어",
        "language": "ko",
        "reference_at": datetime(2026, 7, 15, 12, 0, tzinfo=SEOUL_TIMEZONE),
        "current_latitude": None,
        "current_longitude": None,
        "current_location_name": None,
        "collected": {},
        "latest_user_answer": None,
    }


class TravelIntentExtractorTests(unittest.TestCase):
    def test_route_place_count_is_not_treated_as_ambiguous_budget(self) -> None:
        chain = RunnableLambda(
            lambda _: {
                "language": "ko",
                "intent": "day_trip_route",
                "normalized_question": "내일 홍대 당일 루트 3곳",
                "location": "홍대",
                "start_date": "2026-07-16",
                "end_date": "2026-07-16",
                "days": 1,
                "nights": 0,
                "explicit_visit_count": 3,
                "budget_ambiguous": True,
                "requested_domains": ["restaurant", "attraction", "cafe"],
            }
        )
        state = _base_state()
        state["original_question"] = "내일 홍대에서 총 3곳 당일 루트 짜줘"

        result = asyncio.run(TravelIntentExtractor(chain)(state))

        self.assertFalse(result["collected"]["budget_ambiguous"])
        self.assertNotIn(
            "filters.budget_scope",
            find_missing_fields({**state, **result}),
        )

    def test_location_clarification_accepts_anywhere_without_llm_location(self) -> None:
        chain = RunnableLambda(
            lambda _: {
                "language": "ko",
                "intent": "single_place_recommendation",
                "normalized_question": "식당 추천",
                "requested_domains": ["restaurant"],
            }
        )
        state = _base_state()
        state.update({
            "original_question": "맛있는 식당 추천해줘",
            "intent": "single_place_recommendation",
            "missing_fields": ["filters.location"],
            "latest_user_answer": "장소는 딱히 상관없어요",
        })

        result = asyncio.run(TravelIntentExtractor(chain)(state))

        self.assertEqual(CITYWIDE_LOCATION_NAME, result["collected"]["location"])
        self.assertEqual([], find_missing_fields({**state, **result}))

    def test_input_language_overrides_ui_language(self) -> None:
        chain = RunnableLambda(
            lambda _: {
                "language": "ko",
                "intent": "single_place_recommendation",
                "normalized_question": "Recommend quiet cafes near me",
                "use_current_location": True,
                "requested_domains": ["cafe"],
            }
        )
        state = _base_state()
        state.update(
            {
                "original_question": "Recommend quiet cafes near me",
                "language": "ko",
            }
        )

        result = asyncio.run(TravelIntentExtractor(chain)(state))

        self.assertEqual("en", result["language"])
        self.assertEqual("en", result["collected"]["language"])

    def test_nearby_expression_uses_available_current_coordinates(self) -> None:
        chain = RunnableLambda(
            lambda _: {
                "language": "ko",
                "intent": "single_place_recommendation",
                "normalized_question": "여기 주변 카페 추천",
                "requested_domains": ["cafe"],
            }
        )
        state = _base_state()
        state.update(
            {
                "original_question": "여기 주변 카페 추천해줘.",
                "current_latitude": 37.5563,
                "current_longitude": 126.9236,
            }
        )

        result = asyncio.run(TravelIntentExtractor(chain)(state))

        self.assertTrue(result["collected"]["use_current_location"])
        self.assertEqual([], find_missing_fields(state | result))

    def test_previous_query_and_history_reach_extraction_chain(self) -> None:
        captured: dict = {}

        def followup_extraction(inputs: dict) -> dict:
            captured.update(inputs)
            return {
                "language": "ko",
                "intent": "single_place_recommendation",
                "normalized_question": "강남에서 주차 가능한 식당 추천",
                "location": "강남",
                "requested_domains": ["restaurant"],
                "required_features": ["주차"],
            }

        state = _base_state()
        state.update(
            {
                "original_question": "그중 주차되는 곳만 보여줘",
                "conversation_history": [
                    {"role": "user", "content": "강남 식당 추천해줘"},
                    {"role": "assistant", "content": "세 곳을 추천했습니다."},
                ],
                "previous_structured_query": {
                    "intent": "single_place_recommendation",
                    "filters": {"location": "강남"},
                },
            }
        )

        result = asyncio.run(
            TravelIntentExtractor(RunnableLambda(followup_extraction))(state)
        )

        self.assertIn("강남 식당 추천해줘", captured["conversation_history"])
        self.assertIn("\"location\": \"강남\"", captured["previous_structured_query"])
        self.assertEqual("강남", result["collected"]["location"])
        self.assertEqual(["주차"], result["collected"]["required_features"])

    def test_explicit_slots_become_domains_and_visit_count(self) -> None:
        chain = RunnableLambda(
            lambda _: {
                "language": "ko",
                "intent": "day_trip_route",
                "normalized_question": "2026-07-16 홍대 저녁 식사 후 카페 방문",
                "location": "홍대",
                "start_date": "2026-07-16",
                "requested_slots": [
                    {"domain": "restaurant", "start_time": "19:00"},
                    {"domain": "cafe", "start_time": "21:00"},
                ],
            }
        )

        result = asyncio.run(TravelIntentExtractor(chain)(_base_state()))

        self.assertEqual(2, result["collected"]["explicit_visit_count"])
        self.assertEqual(2, result["collected"]["target_places_per_day"])
        self.assertEqual(
            ["restaurant", "cafe"],
            result["collected"]["requested_domains"],
        )

    def test_explicit_day_slots_fill_deterministic_defaults(self) -> None:
        chain = RunnableLambda(
            lambda _: {
                "language": "ko",
                "intent": "day_trip_route",
                "normalized_question": "2026-07-16 홍대 저녁 식사 후 카페 방문",
                "location": "홍대",
                "start_date": "2026-07-16",
                "explicit_visit_count": 2,
                "requested_domains": ["restaurant", "cafe"],
            }
        )
        extractor = TravelIntentExtractor(chain)

        result = asyncio.run(extractor(_base_state()))

        self.assertEqual("2026-07-16", result["collected"]["end_date"])
        self.assertEqual(0, result["collected"]["nights"])
        self.assertEqual(1, result["collected"]["days"])
        self.assertEqual(2, result["collected"]["target_places_per_day"])
        self.assertEqual("normal", result["collected"]["pace"])

    def test_latest_answer_overrides_previously_collected_value(self) -> None:
        chain = RunnableLambda(
            lambda _: {
                "language": "ko",
                "intent": "single_place_recommendation",
                "normalized_question": "성수 조용한 카페 추천",
                "location": "성수",
                "requested_domains": ["cafe"],
            }
        )
        extractor = TravelIntentExtractor(chain)
        state = _base_state()
        state["collected"] = {"location": "홍대"}
        state["latest_user_answer"] = "홍대 말고 성수로 해줘"

        result = asyncio.run(extractor(state))

        self.assertEqual("성수", result["collected"]["location"])
        self.assertEqual(
            state["original_question"],
            result["collected"]["original_question"],
        )

    def test_day_route_pace_maps_to_target_place_count(self) -> None:
        chain = RunnableLambda(
            lambda _: {
                "language": "ko",
                "intent": "day_trip_route",
                "normalized_question": "2026-07-16 홍대 여유로운 하루 코스",
                "location": "홍대",
                "start_date": "2026-07-16",
                "pace": "relaxed",
            }
        )
        extractor = TravelIntentExtractor(chain)

        result = asyncio.run(extractor(_base_state()))

        self.assertEqual(3, result["collected"]["target_places_per_day"])

    def test_clarification_updates_missing_and_additive_fields_only(self) -> None:
        chain = RunnableLambda(
            lambda _: {
                "language": "ko",
                "intent": "weather_information",
                "normalized_question": "3곳 분위기 좋은",
                "location": "성수",
                "start_date": "2026-07-20",
                "target_places_per_day": 3,
                "pace": "relaxed",
                "themes": ["분위기 좋은"],
            }
        )
        state = _base_state()
        state.update(
            {
                "original_question": "홍대 좋은 코스 추천해줘",
                "intent": "day_trip_route",
                "missing_fields": ["route_request.target_places_per_day"],
                "latest_user_answer": "3곳, 분위기 좋은",
                "conversation_history": [
                    {"role": "assistant", "content": "몇 곳을 방문할까요?"},
                    {"role": "user", "content": "3곳, 분위기 좋은"},
                ],
                "collected": {
                    "location": "홍대",
                    "start_date": "2026-07-16",
                    "end_date": "2026-07-16",
                    "days": 1,
                    "nights": 0,
                },
            }
        )

        result = asyncio.run(TravelIntentExtractor(chain)(state))

        self.assertEqual("day_trip_route", result["intent"])
        self.assertEqual("홍대", result["collected"]["location"])
        self.assertEqual("2026-07-16", result["collected"]["start_date"])
        self.assertEqual(3, result["collected"]["target_places_per_day"])
        self.assertEqual(["분위기 좋은"], result["collected"]["themes"])
        self.assertIn("홍대 좋은 코스 추천해줘", result["normalized_question"])
        self.assertIn("하루 3곳", result["normalized_question"])
        self.assertIn("테마 분위기 좋은", result["normalized_question"])


class RequiredInformationTests(unittest.TestCase):
    def test_single_recommendation_requires_location(self) -> None:
        state = _base_state()
        state["intent"] = "single_place_recommendation"

        result = check_required_information(state)

        self.assertEqual(["filters.location"], result["missing_fields"])
        self.assertEqual("collecting", result["status"])

    def test_current_coordinates_can_satisfy_location(self) -> None:
        state = _base_state()
        state.update(
            {
                "intent": "single_place_recommendation",
                "current_latitude": 37.5563,
                "current_longitude": 126.9236,
                "collected": {"use_current_location": True},
            }
        )

        self.assertEqual([], find_missing_fields(state))

    def test_generic_day_route_asks_for_target_place_count(self) -> None:
        state = _base_state()
        state.update(
            {
                "intent": "day_trip_route",
                "collected": {
                    "location": "홍대",
                    "start_date": "2026-07-16",
                    "end_date": "2026-07-16",
                    "days": 1,
                    "nights": 0,
                },
            }
        )

        result = check_required_information(state)

        self.assertEqual(
            ["route_request.target_places_per_day"],
            result["missing_fields"],
        )
        self.assertIn("3곳", result["assistant_message"])

    def test_explicit_mini_route_can_advance_without_count_question(self) -> None:
        state = _base_state()
        state.update(
            {
                "intent": "day_trip_route",
                "collected": {
                    "location": "홍대",
                    "start_date": "2026-07-16",
                    "end_date": "2026-07-16",
                    "days": 1,
                    "nights": 0,
                    "explicit_visit_count": 2,
                    "target_places_per_day": 2,
                },
            }
        )

        result = check_required_information(state)

        self.assertEqual("building", result["status"])
        self.assertEqual([], result["missing_fields"])

    def test_questions_are_limited_to_two_per_turn(self) -> None:
        state = _base_state()
        state.update(
            {
                "intent": "multi_day_route",
                "collected": {
                    "budget_ambiguous": True,
                    "relative_date_ambiguous": True,
                },
            }
        )

        result = check_required_information(state)

        self.assertGreater(len(result["missing_fields"]), 2)
        self.assertIn("여행할 지역", result["assistant_message"])
        self.assertIn("시작일과 종료일", result["assistant_message"])
        self.assertNotIn("정확한 날짜", result["assistant_message"])

    def test_route_modification_stops_as_unsupported(self) -> None:
        state = _base_state()
        state["intent"] = "modify_route"

        result = check_required_information(state)

        self.assertEqual("unsupported", result["status"])
        self.assertEqual([], result["missing_fields"])
        self.assertEqual(
            ROUTE_MODIFICATION_UNSUPPORTED_MESSAGE,
            result["assistant_message"],
        )
        self.assertIsNone(result["structured_query"])


if __name__ == "__main__":
    unittest.main()
