import json
import unittest
from datetime import date
from unittest.mock import patch

from pydantic import ValidationError

from schemas.route_planner import (
    RouteCandidate,
    RoutePlannerInput,
    RouteRequest,
    RouteSlotCandidates,
    TripPeriod,
)
from services.route_planner import generate_route_plan, validate_route_planner_output


def candidate(candidate_id: str, domain: str = "restaurant") -> RouteCandidate:
    return RouteCandidate(
        candidate_id=candidate_id,
        domain=domain,
        place_id=candidate_id,
        restaurant_id=candidate_id if domain == "restaurant" else None,
        name=f"장소 {candidate_id}",
    )


def planner_input() -> RoutePlannerInput:
    route_request = RouteRequest(
        destination="서울",
        period=TripPeriod(
            start_date=date(2026, 7, 16),
            end_date=date(2026, 7, 16),
            nights=0,
            days=1,
        ),
    )
    slots = [
        RouteSlotCandidates(
            slot_id="day1_dinner",
            day_number=1,
            date=date(2026, 7, 16),
            start_time="19:00",
            domain="restaurant",
            candidates=[candidate(f"r{i}") for i in range(1, 6)],
        ),
        RouteSlotCandidates(
            slot_id="day1_cafe",
            day_number=1,
            date=date(2026, 7, 16),
            start_time="21:00",
            domain="cafe",
            candidates=[candidate(f"c{i}", "cafe") for i in range(1, 6)],
        ),
    ]
    return RoutePlannerInput(
        original_question="내일 홍대 저녁과 카페 일정",
        route_request=route_request,
        slots=slots,
    )


class RoutePlannerSchemaTests(unittest.TestCase):
    def test_period_must_match_dates(self):
        with self.assertRaises(ValidationError):
            TripPeriod(
                start_date=date(2026, 7, 16),
                end_date=date(2026, 7, 18),
                nights=1,
                days=2,
            )

    def test_max_five_slots_per_day(self):
        base = planner_input()
        slots = []
        for index in range(6):
            slots.append(RouteSlotCandidates(
                slot_id=f"s{index}",
                day_number=1,
                date=date(2026, 7, 16),
                start_time=f"{9 + index}:00",
                domain="restaurant",
                candidates=[candidate(f"x{index}")],
            ))
        with self.assertRaises(ValidationError):
            RoutePlannerInput(
                original_question="서울 하루 일정",
                route_request=base.route_request,
                slots=slots,
            )

    def test_slot_date_must_match_day_number(self):
        base = planner_input()
        bad_slot = base.slots[0].model_copy(update={"date": date(2026, 7, 17)})
        with self.assertRaises(ValidationError):
            RoutePlannerInput(
                original_question=base.original_question,
                route_request=base.route_request,
                slots=[bad_slot],
            )

    def test_route_request_max_places_per_day_is_enforced(self):
        base = planner_input()
        request = base.route_request.model_copy(update={"max_places_per_day": 1})
        with self.assertRaises(ValidationError):
            RoutePlannerInput(
                original_question=base.original_question,
                route_request=request,
                slots=base.slots,
            )

    def test_target_places_per_day_cannot_exceed_safety_cap(self):
        with self.assertRaises(ValidationError):
            RouteRequest(
                destination="서울",
                period=TripPeriod(
                    start_date=date(2026, 7, 16),
                    end_date=date(2026, 7, 16),
                    nights=0,
                    days=1,
                ),
                max_places_per_day=2,
                target_places_per_day=3,
            )

    def test_same_place_with_different_candidate_ids_is_rejected(self):
        base = planner_input()
        duplicate = candidate("alias")
        duplicate.place_id = "r1"
        with self.assertRaises(ValidationError):
            RouteSlotCandidates(
                slot_id="duplicate-place",
                day_number=1,
                date=date(2026, 7, 16),
                start_time="19:00",
                domain="restaurant",
                candidates=[candidate("r1"), duplicate],
            )

    def test_time_format_and_order_are_validated(self):
        with self.assertRaises(ValidationError):
            RouteSlotCandidates(
                slot_id="bad-time",
                day_number=1,
                date=date(2026, 7, 16),
                start_time="19시",
                domain="restaurant",
                candidates=[candidate("r1")],
            )

    def test_overnight_accommodation_uses_explicit_end_date(self):
        slot = RouteSlotCandidates(
            slot_id="hotel-night",
            day_number=1,
            date=date(2026, 7, 16),
            start_time="22:00",
            end_date=date(2026, 7, 17),
            end_time="08:00",
            domain="accommodation",
            candidates=[candidate("hotel1", "accommodation")],
        )
        self.assertEqual(slot.start_time, "22:00")
        self.assertEqual(slot.end_time, "08:00")
        with self.assertRaises(ValidationError):
            RouteSlotCandidates(
                slot_id="bad-order",
                day_number=1,
                date=date(2026, 7, 16),
                start_time="20:00",
                end_time="19:00",
                domain="restaurant",
                candidates=[candidate("r1")],
            )


class RoutePlannerValidationTests(unittest.TestCase):
    def test_single_slot_single_candidate_needs_no_alternative(self):
        base = planner_input()
        single = RoutePlannerInput(
            original_question="오늘 저녁 한 곳",
            route_request=base.route_request,
            slots=[base.slots[0].model_copy(update={"candidates": [candidate("only")]})],
        )
        raw = json.dumps({
            "title": "단일 선택",
            "selections": [{
                "slot_id": "day1_dinner",
                "selected_candidate_id": "only",
                "selection_reason": "유일하게 조건을 만족합니다.",
                "alternatives": [],
            }],
        }, ensure_ascii=False)
        result = validate_route_planner_output(raw, single)
        self.assertFalse(result.repaired)
        self.assertEqual(result.slots[0].selected.candidate_id, "only")
        self.assertEqual(result.slots[0].alternatives, [])

    def test_route_llm_failure_falls_back_to_ranked_candidates(self):
        base = planner_input()
        with patch("services.route_planner._client", side_effect=RuntimeError("offline")):
            result = generate_route_plan(base)
        self.assertTrue(result.repaired)
        self.assertEqual(
            [slot.selected.candidate_id for slot in result.slots],
            ["r1", "c1"],
        )
        self.assertEqual(result.slots[0].fallback_candidate_ids, ["r2", "r3"])

    def test_one_malformed_selection_does_not_discard_other_valid_slot(self):
        raw = json.dumps({
            "selections": [
                {"slot_id": "day1_dinner"},
                {
                    "slot_id": "day1_cafe",
                    "selected_candidate_id": "c4",
                    "selection_reason": "정상 카페 선택",
                    "alternatives": [
                        {"candidate_id": "c2", "selection_reason": "정상 대안"}
                    ],
                },
            ]
        }, ensure_ascii=False)
        result = validate_route_planner_output(raw, planner_input())
        self.assertTrue(result.repaired)
        self.assertEqual(result.slots[0].selected.candidate_id, "r1")
        self.assertEqual(result.slots[1].selected.candidate_id, "c4")
        self.assertEqual(result.slots[1].selection_reason, "정상 카페 선택")

    def test_repaired_primary_does_not_reuse_invalid_candidates_alternatives(self):
        raw = json.dumps({
            "selections": [
                {
                    "slot_id": "day1_dinner",
                    "selected_candidate_id": "unknown",
                    "selection_reason": "가짜 대표",
                    "alternatives": [
                        {"candidate_id": "r5", "selection_reason": "가짜 대표에 종속된 대안"}
                    ],
                },
                {"slot_id": "day1_cafe", "selected_candidate_id": "c1", "selection_reason": "카페"},
            ]
        }, ensure_ascii=False)
        result = validate_route_planner_output(raw, planner_input())
        self.assertEqual(result.slots[0].selected.candidate_id, "r1")
        self.assertEqual(result.slots[0].fallback_candidate_ids, ["r2", "r3"])
        self.assertNotIn("가짜", result.slots[0].alternatives[0].selection_reason)

    def test_valid_selection_gets_server_ranked_fallbacks(self):
        raw = json.dumps({
            "title": "홍대 저녁 코스",
            "selections": [
                {"slot_id": "day1_dinner", "selected_candidate_id": "r2", "selection_reason": "분위기가 잘 맞습니다."},
                {"slot_id": "day1_cafe", "selected_candidate_id": "c1", "selection_reason": "동선이 자연스럽습니다.", "alternatives": [
                    {"candidate_id": "c3", "selection_reason": "조용함을 우선한 대안입니다."},
                    {"candidate_id": "c2", "selection_reason": "가까운 대안입니다."}
                ]},
            ],
        }, ensure_ascii=False)
        result = validate_route_planner_output(raw, planner_input())
        # 식당 대안이 누락돼 서버가 채웠으므로 repaired가 기록된다.
        self.assertTrue(result.repaired)
        self.assertEqual(result.slots[0].selected.candidate_id, "r2")
        self.assertEqual(result.slots[0].fallback_candidate_ids, ["r1", "r3"])
        self.assertEqual(result.slots[1].fallback_candidate_ids, ["c3", "c2"])
        self.assertEqual(result.slots[1].alternatives[0].selection_reason, "조용함을 우선한 대안입니다.")
        self.assertEqual(result.alternative_routes, [])

    def test_unknown_duplicate_and_alternative_route_are_repaired(self):
        raw = json.dumps({
            "title": "일정",
            "selections": [
                {"slot_id": "day1_dinner", "selected_candidate_id": "unknown", "selection_reason": "가짜 후보가 최고입니다."},
                {"slot_id": "day1_dinner", "selected_candidate_id": "r2", "selection_reason": "중복 슬롯"},
                {"slot_id": "unknown_slot", "selected_candidate_id": "x", "selection_reason": "가짜"},
            ],
            "alternative_routes": [{"title": "모델이 만든 대안"}],
        }, ensure_ascii=False)
        result = validate_route_planner_output(raw, planner_input())
        self.assertTrue(result.repaired)
        self.assertEqual([slot.selected.candidate_id for slot in result.slots], ["r1", "c1"])
        self.assertEqual(result.slots[0].fallback_candidate_ids, ["r2", "r3"])
        self.assertEqual(result.slots[1].fallback_candidate_ids, ["c2", "c3"])
        self.assertNotIn("가짜 후보", result.slots[0].selection_reason)
        self.assertEqual(result.alternative_routes, [])

    def test_excess_invalid_alternatives_keep_valid_primary_and_are_trimmed(self):
        raw = json.dumps({
            "selections": [
                {
                    "slot_id": "day1_dinner",
                    "selected_candidate_id": "r1",
                    "selection_reason": "대표 이유",
                    "alternatives": [
                        {"candidate_id": "r1", "selection_reason": "대표 중복"},
                        {"candidate_id": "unknown", "selection_reason": "가짜"},
                        {"candidate_id": "r4", "selection_reason": "분위기 대안"},
                        {"candidate_id": "r3", "selection_reason": "가격 대안"},
                    ],
                },
                {
                    "slot_id": "day1_cafe",
                    "selected_candidate_id": "c1",
                    "selection_reason": "카페 대표",
                },
            ]
        }, ensure_ascii=False)
        result = validate_route_planner_output(raw, planner_input())
        self.assertEqual(result.slots[0].selected.candidate_id, "r1")
        self.assertEqual(result.slots[0].fallback_candidate_ids, ["r4", "r3"])
        self.assertEqual(
            [item.selection_reason for item in result.slots[0].alternatives],
            ["분위기 대안", "가격 대안"],
        )
        self.assertTrue(result.repaired)


if __name__ == "__main__":
    unittest.main()
