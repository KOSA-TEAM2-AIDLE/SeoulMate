import unittest
from datetime import datetime
from itertools import permutations
from zoneinfo import ZoneInfo

from application.travel_query.builder import (
    MULTI_DAY_AREA_PROFILES,
    _area_path_distance,
    _area_weight,
    build_structured_query,
)
from models.intent.travel_query import _apply_current_location_hint


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
    def test_explicit_near_me_overrides_misparsed_location_name(self) -> None:
        extracted = {
            "location": "현재",
            "requested_domains": ["attraction"],
        }

        _apply_current_location_hint(
            {
                "original_question": (
                    "현재 내 주변에서 산책하기 좋은 장소를 추천해줘"
                ),
                "latest_user_answer": None,
                "current_latitude": 37.5665,
                "current_longitude": 126.978,
            },
            extracted,
        )

        self.assertTrue(extracted["use_current_location"])
        self.assertIn("location", extracted)
        self.assertIsNone(extracted["location"])

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

    def test_day_route_uses_chronological_default_slot_template(self) -> None:
        result = build_structured_query(
            _state(
                "day_trip_route",
                location="홍대",
                start_date="2026-07-16",
                end_date="2026-07-16",
                nights=0,
                days=1,
                pace="normal",
                target_places_per_day=4,
            )
        )

        self.assertEqual("ready", result["status"])
        tasks = result["structured_query"]["tasks"]
        self.assertEqual(
            ["attraction", "restaurant", "cafe", "attraction"],
            [task["domain"] for task in tasks],
        )
        self.assertEqual(
            ["10:00", "13:00", "16:00", "19:00"],
            [task["start_time"] for task in tasks],
        )

    def test_arrival_and_departure_bounds_fail_before_search(self) -> None:
        arrival_result = build_structured_query(
            _state(
                "day_trip_route",
                location="홍대",
                start_date="2026-07-16",
                end_date="2026-07-16",
                nights=0,
                days=1,
                pace="relaxed",
                target_places_per_day=3,
                arrival_at="20:00",
            )
        )
        departure_result = build_structured_query(
            _state(
                "day_trip_route",
                location="홍대",
                start_date="2026-07-16",
                end_date="2026-07-16",
                nights=0,
                days=1,
                pace="normal",
                target_places_per_day=4,
                departure_at="15:00",
            )
        )

        self.assertEqual("failed", arrival_result["status"])
        self.assertIn("arrival_at", " ".join(arrival_result["validation_errors"]))
        self.assertEqual("failed", departure_result["status"])
        self.assertIn("departure_at", " ".join(departure_result["validation_errors"]))

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

    def test_multi_day_route_excludes_accommodation_and_builds_five_activities(self) -> None:
        result = build_structured_query(
            _state(
                "multi_day_route",
                location="서울",
                start_date="2026-08-01",
                end_date="2026-08-03",
                nights=2,
                days=3,
                pace="normal",
            )
        )

        self.assertEqual("ready", result["status"])
        tasks = result["structured_query"]["tasks"]
        self.assertEqual(15, len(tasks))
        self.assertFalse(any(task["domain"] == "accommodation" for task in tasks))
        for day_number in range(1, 4):
            day_tasks = [task for task in tasks if task["day_number"] == day_number]
            self.assertEqual(5, len(day_tasks))
            self.assertEqual(
                ["attraction", "restaurant", "cafe", "attraction", "restaurant"],
                [task["domain"] for task in day_tasks],
            )
            self.assertEqual(
                ["10:00", "12:30", "15:00", "17:00", "19:00"],
                [task["start_time"] for task in day_tasks],
            )

    def test_citywide_multi_day_route_assigns_one_area_per_day(self) -> None:
        state = _state(
            "multi_day_route",
            location="아무곳",
            start_date="2026-08-01",
            end_date="2026-08-05",
            nights=4,
            days=5,
            pace="normal",
        )
        result = build_structured_query(state)
        repeated = build_structured_query(state)

        self.assertEqual("ready", result["status"])
        query = result["structured_query"]
        expected_areas = query["route_request"]["preferred_areas"]
        self.assertEqual("서울 전체", query["filters"]["location"])
        self.assertEqual("서울 전체", query["route_request"]["destination"])
        self.assertEqual(5, len(expected_areas))
        self.assertEqual(5, len(set(expected_areas)))
        self.assertTrue(set(expected_areas) <= set(MULTI_DAY_AREA_PROFILES))
        self.assertEqual(
            expected_areas,
            repeated["structured_query"]["route_request"]["preferred_areas"],
        )
        self.assertEqual(
            _area_path_distance(tuple(expected_areas)),
            min(_area_path_distance(route) for route in permutations(expected_areas)),
        )
        for day_number, expected_area in enumerate(expected_areas, start=1):
            day_tasks = [
                task for task in query["tasks"]
                if task["day_number"] == day_number
            ]
            self.assertTrue(day_tasks)
            self.assertTrue(all(
                task["filters"]["location"] == expected_area
                for task in day_tasks
            ))
            self.assertTrue(all(
                expected_area in task["search_query"]
                for task in day_tasks
            ))

    def test_citywide_area_weights_favor_popular_well_covered_areas(self) -> None:
        self.assertGreater(_area_weight("강남구"), _area_weight("광진구"))
        self.assertGreater(_area_weight("종로구"), _area_weight("영등포구"))

    def test_multiple_preferred_areas_are_assigned_to_separate_days(self) -> None:
        result = build_structured_query(
            _state(
                "multi_day_route",
                start_date="2026-08-01",
                end_date="2026-08-05",
                nights=4,
                days=5,
                pace="normal",
                requested_slots=[
                    {"domain": "attraction", "location": "강남"},
                    {"domain": "attraction", "location": "홍대"},
                ],
            )
        )

        self.assertEqual("ready", result["status"])
        query = result["structured_query"]
        self.assertEqual("강남", query["route_request"]["destination"])
        assigned_areas = query["route_request"]["preferred_areas"]
        self.assertIn("강남구", assigned_areas)
        self.assertIn("마포구", assigned_areas)
        self.assertEqual(5, len(assigned_areas))
        self.assertEqual(5, len(set(assigned_areas)))
        for day_number, assigned_area in enumerate(assigned_areas, start=1):
            day_tasks = [
                task for task in query["tasks"]
                if task["day_number"] == day_number
            ]
            self.assertEqual(5, len(day_tasks))
            self.assertEqual(
                {assigned_area},
                {task["filters"]["location"] for task in day_tasks},
            )

    def test_specific_multi_day_location_is_not_replaced_by_default_area(self) -> None:
        result = build_structured_query(
            _state(
                "multi_day_route",
                location="홍대",
                start_date="2026-08-01",
                end_date="2026-08-02",
                nights=1,
                days=2,
                pace="relaxed",
            )
        )

        self.assertEqual("ready", result["status"])
        query = result["structured_query"]
        self.assertEqual(["홍대"], query["route_request"]["preferred_areas"])
        self.assertTrue(all(task["filters"] is None for task in query["tasks"]))

    def test_accommodation_only_route_request_uses_activity_mix(self) -> None:
        result = build_structured_query(
            _state(
                "multi_day_route",
                location="서울",
                start_date="2026-08-01",
                end_date="2026-08-02",
                nights=1,
                days=2,
                pace="normal",
                requested_domains=["accommodation"],
            )
        )

        self.assertEqual("ready", result["status"])
        tasks = result["structured_query"]["tasks"]
        day_one = [task for task in tasks if task["day_number"] == 1]
        day_two = [task for task in tasks if task["day_number"] == 2]
        self.assertEqual(5, len(day_one))
        self.assertEqual(5, len(day_two))
        self.assertTrue(all(task["domain"] != "accommodation" for task in tasks))

    def test_explicit_final_day_accommodation_is_excluded_from_route(self) -> None:
        result = build_structured_query(
            _state(
                "multi_day_route",
                location="서울",
                start_date="2026-08-01",
                end_date="2026-08-02",
                nights=1,
                days=2,
                pace="relaxed",
                requested_slots=[{
                    "domain": "accommodation",
                    "day_number": 2,
                    "visit_date": "2026-08-02",
                }],
            )
        )

        self.assertEqual("ready", result["status"])
        self.assertFalse(any(
            task["domain"] == "accommodation"
            for task in result["structured_query"]["tasks"]
        ))

    def test_explicit_accommodation_is_removed_from_relaxed_route(self) -> None:
        result = build_structured_query(
            _state(
                "multi_day_route",
                location="서울",
                start_date="2026-08-01",
                end_date="2026-08-02",
                nights=1,
                days=2,
                pace="relaxed",
                requested_slots=[
                    {"domain": "attraction", "day_number": 1},
                    {"domain": "restaurant", "day_number": 1},
                    {"domain": "cafe", "day_number": 1},
                    {"domain": "accommodation", "day_number": 1},
                ],
            )
        )

        self.assertEqual("ready", result["status"])
        day_one = [
            task
            for task in result["structured_query"]["tasks"]
            if task["day_number"] == 1
        ]
        self.assertEqual(
            ["attraction", "restaurant", "cafe"],
            [task["domain"] for task in day_one],
        )

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
