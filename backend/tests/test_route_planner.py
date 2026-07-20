import json
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from schemas.route_planner import (
    RouteCandidate,
    RoutePlannerInput,
    RouteRequest,
    RouteSlotCandidates,
    TripPeriod,
)
from services.route_planner import (
    ROUTE_SUMMARY_MAX_OUTPUT_TOKENS,
    generate_route_plan,
    route_planner_payload,
    route_summary_payload,
    validate_route_planner_output,
)


def candidate(
    candidate_id: str,
    domain: str = "restaurant",
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> RouteCandidate:
    return RouteCandidate(
        candidate_id=candidate_id,
        domain=domain,
        place_id=candidate_id,
        restaurant_id=candidate_id if domain == "restaurant" else None,
        name=f"장소 {candidate_id}",
        latitude=latitude,
        longitude=longitude,
    )


def spatial_planner_input(*, include_second_slot_coordinates: bool = True):
    base = planner_input()
    second_coordinates = (
        {"latitude": 37.5, "longitude": 127.2},
        {"latitude": 37.5, "longitude": 127.051},
    ) if include_second_slot_coordinates else ({}, {})
    slots = [
        base.slots[0].model_copy(update={
            "slot_id": "first",
            "start_time": "10:00",
            "candidates": [
                candidate("a1", latitude=37.5, longitude=127.0),
                candidate("a2", latitude=37.5, longitude=127.05),
            ],
        }),
        base.slots[1].model_copy(update={
            "slot_id": "second",
            "start_time": "14:00",
            "candidates": [
                candidate("b1", "cafe", **second_coordinates[0]),
                candidate("b2", "cafe", **second_coordinates[1]),
            ],
        }),
    ]
    return RoutePlannerInput(
        original_question="이동이 짧은 두 곳",
        route_request=base.route_request,
        slots=slots,
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
    def test_candidate_coordinates_must_be_paired(self):
        with self.assertRaisesRegex(ValidationError, "함께 제공"):
            candidate("half-coordinate", latitude=37.5)

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

    def test_arrival_and_departure_bound_route_slots(self):
        base = planner_input()
        late_arrival = RouteRequest.model_validate({
            **base.route_request.model_dump(),
            "arrival_at": "20:00",
        })
        with self.assertRaisesRegex(ValidationError, "arrival_at"):
            RoutePlannerInput(
                original_question=base.original_question,
                route_request=late_arrival,
                slots=base.slots,
            )

        early_departure = RouteRequest.model_validate({
            **base.route_request.model_dump(),
            "departure_at": "20:00",
        })
        with self.assertRaisesRegex(ValidationError, "departure_at"):
            RoutePlannerInput(
                original_question=base.original_question,
                route_request=early_departure,
                slots=base.slots,
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
    def test_shifted_windows_keep_five_day_restaurant_route_unique(self):
        period = TripPeriod(
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 5),
            nights=4,
            days=5,
        )
        request = RouteRequest(destination="서울", period=period)
        ranked = [candidate(f"restaurant-{index}") for index in range(14)]
        slots = []
        for occurrence in range(10):
            day_number = occurrence // 2 + 1
            slots.append(RouteSlotCandidates(
                slot_id=f"day{day_number}-restaurant-{occurrence}",
                day_number=day_number,
                date=date(2026, 8, day_number),
                start_time="12:00" if occurrence % 2 == 0 else "19:00",
                domain="restaurant",
                candidates=ranked[occurrence:occurrence + 5],
            ))
        planner = RoutePlannerInput(
            original_question="서울 4박 5일 맛집 일정",
            route_request=request,
            slots=slots,
        )

        result = validate_route_planner_output("{}", planner)

        selected_place_ids = [slot.selected.place_id for slot in result.slots]
        self.assertEqual(len(selected_place_ids), 10)
        self.assertEqual(len(set(selected_place_ids)), 10)
        self.assertEqual(
            selected_place_ids,
            [f"restaurant-{index}" for index in range(10)],
        )

    def test_payload_contains_coordinates_and_adjacent_distance_matrix(self):
        payload = route_planner_payload(spatial_planner_input())

        self.assertEqual(
            payload["route_optimization"]["chronological_slot_ids"],
            ["first", "second"],
        )
        self.assertEqual(
            payload["slots"][0]["candidates"][0]["latitude"],
            37.5,
        )
        matrix = payload["route_optimization"]["adjacent_slot_matrices"][0]
        self.assertEqual(matrix["from_slot_id"], "first")
        self.assertEqual(matrix["to_slot_id"], "second")
        self.assertEqual(len(matrix["distances"]), 4)
        self.assertTrue(all(item["distance_km"] >= 0 for item in matrix["distances"]))

    def test_gpt_receives_only_confirmed_places_and_compact_weather(self):
        planner = spatial_planner_input().model_copy(update={
            "weather_by_day": [{
                "date": "2026-07-16",
                "time": "14:00",
                "available": True,
                "condition": "rain",
                "temperature_c": 24.0,
                "precipitation_probability_pct": 70,
                "usage_guidance": ["실내 장소 우선", "우산 준비", "긴 설명 제외"],
                "irrelevant_raw_payload": "x" * 10000,
            }],
        })
        response = SimpleNamespace(output_text=json.dumps({
            "title": "비 오는 날의 서울 일정",
            "summary": "비 예보와 이동 거리를 고려해 두 장소를 연결했습니다. 이동 전 강수 상황을 확인해 주세요.",
        }, ensure_ascii=False))
        client = SimpleNamespace(
            responses=SimpleNamespace(create=lambda **kwargs: response)
        )
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            return response

        client.responses.create = create
        with patch("services.route_planner._client", return_value=client):
            result = generate_route_plan(planner)

        payload = json.loads(captured["input"])
        self.assertNotIn("slots", payload)
        self.assertNotIn("route_optimization", payload)
        self.assertNotIn("irrelevant_raw_payload", captured["input"])
        self.assertEqual(
            [item["name"] for item in payload["itinerary"]],
            [slot.selected.name for slot in result.slots],
        )
        self.assertEqual(payload["weather"][0]["condition"], "rain")
        self.assertEqual(payload["weather"][0]["temperature_c"], 24.0)
        self.assertLess(len(captured["input"]), 5000)
        self.assertEqual(
            captured["max_output_tokens"],
            ROUTE_SUMMARY_MAX_OUTPUT_TOKENS,
        )
        self.assertEqual(captured["reasoning"], {"effort": "minimal"})
        self.assertEqual(result.title, "비 오는 날의 서울 일정")
        # 이유를 돌려주지 않은 응답이므로 슬롯별 GPT 이유는 비어 있어야 한다.
        self.assertEqual(result.llm_selection_reasons, {})

    def _plan_with_summary_response(self, body: dict):
        planner = spatial_planner_input()
        response = SimpleNamespace(
            output_text=json.dumps(body, ensure_ascii=False)
        )
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            return response

        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        with patch("services.route_planner._client", return_value=client):
            return generate_route_plan(planner), captured

    def test_confirmed_slot_facts_are_sent_for_reason_writing(self):
        _, captured = self._plan_with_summary_response({
            "title": "서울 하루 일정",
            "summary": "가까운 두 곳을 이어 구성했습니다. 이동 시간을 확인해 주세요.",
        })
        payload = json.loads(captured["input"])
        first, second = payload["itinerary"]
        # 이유를 슬롯에 정확히 매칭하려면 slot_id가 반드시 있어야 한다.
        self.assertEqual(first["slot_id"], "first")
        self.assertEqual(second["slot_id"], "second")
        # 같은 날 연속 구간은 직전 일정과의 거리를 근거로 제공한다.
        self.assertNotIn("distance_from_previous_km", first)
        self.assertIn("distance_from_previous_km", second)

    def test_llm_reasons_are_kept_only_for_known_slots(self):
        plan, _ = self._plan_with_summary_response({
            "title": "서울 하루 일정",
            "summary": "가까운 두 곳을 이어 구성했습니다. 이동 시간을 확인해 주세요.",
            "reasons": [
                {"slot_id": "first", "selection_reason": "평점이 높고 오전에 여유롭습니다."},
                {"slot_id": "second", "selection_reason": "   "},
                {"slot_id": "존재하지않는슬롯", "selection_reason": "무시되어야 합니다."},
            ],
        })
        # 빈 이유와 모르는 슬롯은 버리고, 남은 슬롯은 호출부가 폴백으로 채운다.
        self.assertEqual(
            plan.llm_selection_reasons,
            {"first": "평점이 높고 오전에 여유롭습니다."},
        )

    def test_llm_failure_keeps_route_without_reasons(self):
        planner = spatial_planner_input()
        client = SimpleNamespace(responses=SimpleNamespace(
            create=lambda **kwargs: (_ for _ in ()).throw(TimeoutError()),
        ))
        with patch("services.route_planner._client", return_value=client):
            plan = generate_route_plan(planner)
        self.assertEqual(plan.llm_selection_reasons, {})
        self.assertTrue(plan.title)
        self.assertTrue(plan.summary)
        self.assertEqual(len(plan.slots), 2)

    def test_day_boundary_is_connected_only_from_accommodation(self):
        period = TripPeriod(
            start_date=date(2026, 7, 16),
            end_date=date(2026, 7, 17),
            nights=1,
            days=2,
        )
        request = RouteRequest(destination="서울", period=period)
        day_two = RouteSlotCandidates(
            slot_id="day2-first",
            day_number=2,
            date=date(2026, 7, 17),
            start_time="10:00",
            domain="cafe",
            candidates=[candidate("c1", "cafe", latitude=37.51, longitude=127.01)],
        )
        day_one_activity = RouteSlotCandidates(
            slot_id="day1-last",
            day_number=1,
            date=date(2026, 7, 16),
            start_time="19:00",
            domain="restaurant",
            candidates=[candidate("r1", latitude=37.5, longitude=127.0)],
        )
        without_hotel = RoutePlannerInput(
            original_question="숙소 없는 1박 2일",
            route_request=request,
            slots=[day_one_activity, day_two],
        )
        self.assertEqual(
            route_planner_payload(without_hotel)["route_optimization"]
            ["adjacent_slot_matrices"],
            [],
        )

        hotel = RouteSlotCandidates(
            slot_id="hotel",
            day_number=1,
            date=date(2026, 7, 16),
            start_time="22:00",
            end_date=date(2026, 7, 17),
            end_time="08:00",
            domain="accommodation",
            candidates=[candidate(
                "h1",
                "accommodation",
                latitude=37.505,
                longitude=127.005,
            )],
        )
        with_hotel = RoutePlannerInput(
            original_question="숙소 있는 1박 2일",
            route_request=request,
            slots=[day_one_activity, hotel, day_two],
        )
        edges = route_planner_payload(with_hotel)["route_optimization"][
            "adjacent_slot_matrices"
        ]
        self.assertEqual(
            [(edge["from_slot_id"], edge["to_slot_id"]) for edge in edges],
            [("day1-last", "hotel"), ("hotel", "day2-first")],
        )

    def test_server_optimizes_ranked_candidates_by_consecutive_distance(self):
        spatial = spatial_planner_input()
        with patch("services.route_planner._client", side_effect=RuntimeError("offline")):
            result = generate_route_plan(spatial)

        self.assertEqual(
            [slot.selected.candidate_id for slot in result.slots],
            ["a2", "b2"],
        )
        self.assertTrue(result.route_optimized)
        self.assertEqual(result.distance_method, "haversine")
        self.assertEqual(result.coordinate_coverage, 1.0)
        self.assertLess(result.travel_distance_km, 0.2)

    def test_missing_slot_coordinates_keeps_safe_rank_fallback(self):
        spatial = spatial_planner_input(include_second_slot_coordinates=False)
        with patch("services.route_planner._client", side_effect=RuntimeError("offline")):
            result = generate_route_plan(spatial)

        self.assertEqual(
            [slot.selected.candidate_id for slot in result.slots],
            ["a1", "b1"],
        )
        self.assertFalse(result.route_optimized)
        self.assertIsNone(result.travel_distance_km)
        self.assertIsNone(result.distance_method)
        self.assertEqual(result.coordinate_coverage, 0.5)

    def test_coordinate_gap_does_not_disable_later_route_legs(self):
        base = planner_input()
        slots = [
            RouteSlotCandidates(
                slot_id="morning",
                day_number=1,
                date=date(2026, 7, 16),
                start_time="10:00",
                domain="attraction",
                candidates=[candidate(
                    "morning-1", "attraction", latitude=37.48, longitude=127.0
                )],
            ),
            RouteSlotCandidates(
                slot_id="cafe-without-coordinates",
                day_number=1,
                date=date(2026, 7, 16),
                start_time="15:00",
                domain="cafe",
                candidates=[candidate("mock-cafe", "cafe")],
            ),
            RouteSlotCandidates(
                slot_id="afternoon",
                day_number=1,
                date=date(2026, 7, 16),
                start_time="17:00",
                domain="attraction",
                candidates=[candidate(
                    "afternoon-1", "attraction", latitude=37.5, longitude=127.0
                )],
            ),
            RouteSlotCandidates(
                slot_id="dinner",
                day_number=1,
                date=date(2026, 7, 16),
                start_time="19:00",
                domain="restaurant",
                candidates=[
                    candidate("far", latitude=37.6, longitude=127.0),
                    candidate("near", latitude=37.501, longitude=127.0),
                ],
            ),
        ]
        planner = RoutePlannerInput(
            original_question="좌표 없는 카페가 포함된 저녁 동선",
            route_request=base.route_request,
            slots=slots,
        )

        with patch("services.route_planner._client", side_effect=RuntimeError("offline")):
            result = generate_route_plan(planner)

        self.assertTrue(result.route_optimized)
        self.assertEqual("mock-cafe", result.slots[1].selected.candidate_id)
        self.assertEqual("near", result.slots[3].selected.candidate_id)
        self.assertLess(result.travel_distance_km, 1.0)

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
