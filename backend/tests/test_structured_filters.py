import unittest
from dataclasses import replace
from datetime import datetime
from unittest.mock import patch

from schemas.structured_query import StructuredTravelQuery
from services.rag import (
    _extract_required_menu_terms,
    _ids_with_required_menus,
    _passes_candidate_filters,
    build_restaurant_search_plan,
)


def _parsed(question: str = "홍대 식당 추천") -> StructuredTravelQuery:
    return StructuredTravelQuery.model_validate({
        "language": "ko",
        "intent": "single_place_recommendation",
        "original_question": question,
        "normalized_question": question,
        "tasks": [{
            "task_id": "task_1",
            "domain": "restaurant",
            "search_query": "홍대 식당",
            "themes": [],
            "desired_count": 3,
        }],
        "filters": {"location": "홍대"},
    })


def _plan():
    parsed = _parsed()
    return build_restaurant_search_plan(parsed, parsed.tasks[0])


def _meta(**updates):
    value = {
        "rating": 4.6,
        "menu_price_median": 25_000,
        "menu_price_lo": 20_000,
        "menu_price_hi": 30_000,
        "has_parking": True,
        "allows_pets": False,
        "has_kids_menu": False,
        "has_group_seating": True,
        "has_private_room": True,
        "has_baby_chair": False,
        "has_disabled_access": True,
        "hours": "월 09:00~23:00",
    }
    value.update(updates)
    return value


class StructuredCandidateFilterTests(unittest.TestCase):
    def test_min_rating_is_a_hard_filter_and_unknown_rating_does_not_pass(self):
        plan = _plan()
        for rating, expected in ((4.5, True), (4.4, False), (None, False)):
            with self.subTest(rating=rating), patch(
                "services.rag.is_open_now", return_value=True
            ):
                passed, _, _ = _passes_candidate_filters(
                    _meta(rating=rating), plan, min_rating=4.5, open_now=False
                )
            self.assertEqual(passed, expected)

    def test_required_feature_accepts_only_explicit_true(self):
        plan = replace(_plan(), required_feature_fields=("has_parking",))
        for value, expected in ((True, True), (False, False), (None, False)):
            with self.subTest(value=value), patch(
                "services.rag.is_open_now", return_value=True
            ):
                passed, _, _ = _passes_candidate_filters(
                    _meta(has_parking=value), plan, min_rating=None, open_now=False
                )
            self.assertEqual(passed, expected)

    def test_excluded_feature_rejects_only_explicit_true(self):
        plan = replace(_plan(), excluded_feature_fields=("allows_pets",))
        for value, expected in ((True, False), (False, True), (None, True)):
            with self.subTest(value=value), patch(
                "services.rag.is_open_now", return_value=True
            ):
                passed, _, _ = _passes_candidate_filters(
                    _meta(allows_pets=value), plan, min_rating=None, open_now=False
                )
            self.assertEqual(passed, expected)

    def test_budget_range_uses_menu_range_and_unknown_price_does_not_pass(self):
        plan = replace(_plan(), budget_min_krw=20_000, budget_max_krw=30_000)
        for price, expected in (
            (20_000, True), (25_000, True), (30_000, True),
            (19_999, False), (30_001, False), (None, False),
        ):
            with self.subTest(price=price), patch(
                "services.rag.is_open_now", return_value=True
            ):
                passed, _, _ = _passes_candidate_filters(
                    _meta(menu_price_lo=price, menu_price_hi=price),
                    plan,
                    min_rating=None,
                    open_now=False,
                )
            self.assertEqual(passed, expected)

    def test_budget_max_accepts_when_menu_range_overlaps_budget(self):
        plan = replace(_plan(), budget_max_krw=20_000)
        with patch("services.rag.is_open_now", return_value=True):
            passed, _, _ = _passes_candidate_filters(
                _meta(menu_price_lo=10_000, menu_price_hi=30_000),
                plan,
                min_rating=None,
                open_now=False,
            )
        self.assertTrue(passed)

    def test_budget_max_accepts_restaurant_when_menu_range_is_within_budget(self):
        plan = replace(_plan(), budget_max_krw=20_000)
        with patch("services.rag.is_open_now", return_value=True):
            passed, _, _ = _passes_candidate_filters(
                _meta(menu_price_lo=10_000, menu_price_hi=18_000),
                plan,
                min_rating=None,
                open_now=False,
            )
        self.assertTrue(passed)

    def test_open_now_rejects_closed_and_unknown_hours(self):
        plan = _plan()
        for status, expected in ((True, True), (False, False), (None, False)):
            with self.subTest(status=status), patch(
                "services.rag.is_open_now", return_value=status
            ):
                passed, observed, basis = _passes_candidate_filters(
                    _meta(), plan, min_rating=None, open_now=True
                )
            self.assertEqual(passed, expected)
            self.assertEqual(observed, status)
            self.assertEqual(basis, "now")

    def test_future_visit_rejects_confirmed_closed_but_keeps_unknown_as_fallback(self):
        target = datetime(2026, 7, 18, 19, 0)
        plan = replace(_plan(), target_visit_at=target)
        for status, expected in ((True, True), (False, False), (None, True)):
            with self.subTest(status=status), patch(
                "services.rag.is_open_at", return_value=status
            ):
                passed, observed, basis = _passes_candidate_filters(
                    _meta(), plan, min_rating=None, open_now=False
                )
            self.assertEqual(passed, expected)
            self.assertEqual(observed, status)
            self.assertEqual(basis, "requested_time")


class StructuredFilterPlanTests(unittest.TestCase):
    def test_semantic_preferences_do_not_become_boolean_facility_filters(self):
        parsed = _parsed("홍대에서 조용하고 분위기 좋은 식당 추천")
        parsed.tasks[0].themes = ["조용한", "분위기 좋은"]
        parsed.filters.required_features = ["조용한", "분위기 좋은"]
        plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertEqual(plan.required_feature_fields, ())

    def test_real_facility_filters_are_mapped_without_semantic_noise(self):
        parsed = _parsed("홍대에서 주차 가능하고 휠체어 접근 가능한 식당 추천")
        parsed.filters.required_features = ["주차 가능", "휠체어 접근 가능", "조용한"]
        parsed.filters.excluded_features = ["반려동물 동반"]
        plan = build_restaurant_search_plan(parsed, parsed.tasks[0])
        self.assertEqual(
            set(plan.required_feature_fields),
            {"has_parking", "has_disabled_access"},
        )
        self.assertEqual(plan.excluded_feature_fields, ("allows_pets",))

    def test_specific_menu_is_hard_constraint_but_cuisine_is_not(self):
        self.assertEqual(_extract_required_menu_terms("홍대 마라탕 식당", "ko"), ("마라탕",))
        self.assertEqual(_extract_required_menu_terms("홍대 중식당", "ko"), ())

        class Cursor:
            def __init__(self):
                self.sql = None
                self.params = None

            def execute(self, sql, params):
                self.sql = sql
                self.params = params

            def fetchall(self):
                return [{"restaurant_id": 10}, {"restaurant_id": 20}]

        cursor = Cursor()
        ids = _ids_with_required_menus(cursor, "ko", ("마라탕",), [10, 20, 30])
        self.assertEqual(ids, [10, 20])
        self.assertIn("restaurant_menu_ko", cursor.sql)
        self.assertIn("restaurant_id = ANY", cursor.sql)
        self.assertEqual(cursor.params, ["%마라탕%", [10, 20, 30]])


if __name__ == "__main__":
    unittest.main()
