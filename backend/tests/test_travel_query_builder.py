import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from application.travel_query.builder import build_structured_query


REFERENCE_AT = datetime(2026, 7, 15, 12, 0, tzinfo=ZoneInfo("Asia/Seoul"))


def _state(intent: str, **collected: object) -> dict:
    return {
        "status": "building",
        "original_question": "사용자 원문",
        "normalized_question": "정규화된 질문",
        "language": "ko",
        "intent": intent,
        "reference_at": REFERENCE_AT,
        "collected": {
            "intent": intent,
            "original_question": "사용자 원문",
            "language": "ko",
            **collected,
        },
    }


class StructuredTravelQueryBuilderTests(unittest.TestCase):
    def test_recommendation_without_domain_fails_instead_of_dispatching_etc(self) -> None:
        result = build_structured_query(_state(
            "single_place_recommendation", location="경복궁",
        ))

        self.assertEqual("failed", result["status"])
        self.assertIsNone(result["structured_query"])
        self.assertIn("검색 도메인", " ".join(result["validation_errors"]))

    def test_single_recommendation_builds_three_choice_task(self) -> None:
        result = build_structured_query(
            _state(
                "single_place_recommendation",
                location="성수",
                requested_domains=["cafe"],
                themes=["조용한"],
            )
        )

        self.assertEqual("ready", result["status"])
        query = result["structured_query"]
        self.assertEqual("사용자 원문", query["original_question"])
        self.assertEqual(3, query["tasks"][0]["desired_count"])
        self.assertEqual("성수 조용한 카페", query["tasks"][0]["search_query"])
        self.assertTrue(query["filters"]["is_active"])

    def test_day_route_builds_exact_target_number_of_slots(self) -> None:
        result = build_structured_query(
            _state(
                "day_trip_route",
                location="홍대",
                start_date="2026-07-16",
                end_date="2026-07-16",
                nights=0,
                days=1,
                pace="normal",
                target_places_per_day=2,
                requested_domains=["restaurant", "cafe"],
                themes=["분위기 좋은"],
                requested_slots=[
                    {
                        "domain": "restaurant",
                        "themes": ["저녁", "식사"],
                        "start_time": "19:00",
                        "end_time": "20:30",
                    },
                    {
                        "domain": "cafe",
                        "themes": ["분위기 좋은"],
                        "start_time": "21:00",
                        "end_time": "22:00",
                    },
                ],
            )
        )

        query = result["structured_query"]
        self.assertEqual("ready", result["status"])
        self.assertEqual(2, len(query["tasks"]))
        self.assertEqual([1, 1], [task["desired_count"] for task in query["tasks"]])
        self.assertEqual(
            ["d1-restaurant-1", "d1-cafe-1"],
            [task["slot_id"] for task in query["tasks"]],
        )
        self.assertEqual(2, query["route_request"]["target_places_per_day"])
        self.assertEqual("2026-07-16", query["weather_request"]["target_date"])
        dumped_tasks = query["tasks"]
        self.assertEqual("19:00", dumped_tasks[0]["start_time"])
        self.assertEqual("22:00", dumped_tasks[1]["end_time"])

    def test_multi_day_route_keeps_target_null_and_limits_each_day(self) -> None:
        result = build_structured_query(
            _state(
                "multi_day_route",
                location="서울",
                start_date="2026-08-01",
                end_date="2026-08-02",
                nights=1,
                days=2,
                pace="relaxed",
                requested_domains=["attraction", "restaurant", "cafe"],
            )
        )

        query = result["structured_query"]
        self.assertEqual("ready", result["status"])
        self.assertEqual(6, len(query["tasks"]))
        self.assertEqual(
            [1, 1, 1, 2, 2, 2],
            [task["day_number"] for task in query["tasks"]],
        )
        self.assertIsNone(query["route_request"]["target_places_per_day"])

    def test_undated_explicit_slot_is_not_duplicated_on_every_day(self) -> None:
        result = build_structured_query(
            _state(
                "multi_day_route",
                location="서울",
                start_date="2026-08-01",
                end_date="2026-08-02",
                nights=1,
                days=2,
                pace="relaxed",
                requested_domains=["attraction"],
                requested_slots=[
                    {"domain": "cafe", "themes": ["꼭 가고 싶은"]},
                    {
                        "domain": "restaurant",
                        "visit_date": "2026-08-02",
                        "themes": ["저녁"],
                    },
                ],
            )
        )

        tasks = result["structured_query"]["tasks"]
        self.assertEqual("cafe", tasks[0]["domain"])
        self.assertEqual("restaurant", tasks[3]["domain"])
        self.assertEqual(1, sum(task["domain"] == "cafe" for task in tasks))

    def test_weather_intent_does_not_create_place_task(self) -> None:
        result = build_structured_query(
            _state(
                "weather_information",
                location="성수",
                start_date="2026-07-16",
                target_time="15:00",
            )
        )

        query = result["structured_query"]
        self.assertEqual("ready", result["status"])
        self.assertEqual([], query["tasks"])
        self.assertEqual("성수", query["weather_request"]["location_name"])
        self.assertEqual("15:00", query["weather_request"]["target_time"])

    def test_validation_failure_never_exposes_partial_query(self) -> None:
        result = build_structured_query(
            _state(
                "day_trip_route",
                location="홍대",
                start_date="2026-07-16",
                end_date="2026-07-16",
                nights=0,
                days=1,
            )
        )

        self.assertEqual("failed", result["status"])
        self.assertIsNone(result["structured_query"])
        self.assertTrue(result["validation_errors"])


if __name__ == "__main__":
    unittest.main()
