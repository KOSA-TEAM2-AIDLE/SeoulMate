import unittest

from application.travel_query.builder import build_structured_query
from application.travel_query.validation import (
    classify_build_failure,
    repair_confirmed_values,
)
from tests.test_travel_query_builder import _state


class TravelQueryValidationTests(unittest.TestCase):
    def test_safe_time_format_is_repaired_once(self) -> None:
        state = _state(
            "day_trip_route",
            location="홍대",
            start_date="2026/07/16",
            end_date="2026/07/16",
            nights=0,
            days=1,
            target_places_per_day=1,
            requested_slots=[
                {"domain": "restaurant", "start_time": "9:00:00"},
            ],
        )
        failed = {**state, **build_structured_query(state)}

        classified = classify_build_failure(failed)
        repaired = repair_confirmed_values({**failed, **classified})
        rebuilt = build_structured_query({**failed, **classified, **repaired})

        self.assertEqual("repairing", classified["status"])
        self.assertEqual(1, repaired["repair_attempts"])
        self.assertEqual("ready", rebuilt["status"])
        self.assertEqual("09:00", rebuilt["structured_query"].tasks[0].start_time)

    def test_budget_range_error_returns_to_user_question(self) -> None:
        state = _state(
            "single_place_recommendation",
            location="성수",
            requested_domains=["cafe"],
            budget_min_krw=50000,
            budget_max_krw=10000,
        )
        failed = {**state, **build_structured_query(state)}

        classified = classify_build_failure(failed)

        self.assertEqual("collecting", classified["status"])
        self.assertEqual(["filters.budget_range"], classified["missing_fields"])
        self.assertIn("최소 예산", classified["assistant_message"])

    def test_second_unknown_failure_stops_without_looping(self) -> None:
        state = {
            **_state("single_place_recommendation", location="성수"),
            "status": "failed",
            "validation_errors": ["unknown schema error"],
            "repair_attempts": 1,
        }

        result = classify_build_failure(state)

        self.assertEqual("failed", result["status"])


if __name__ == "__main__":
    unittest.main()
