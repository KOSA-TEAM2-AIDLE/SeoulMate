import unittest

from pydantic import ValidationError

from application.response.frontend_response_mapper import (
    empty_frontend_response,
    recommendation_frontend_response,
    route_frontend_response,
)
from schemas.chat import DayPlan, TimeSlot
from schemas.common import Place
from schemas.frontend_response import FrontendResponse


def place(
    place_id: str,
    *,
    source_type: str = "restaurant",
    rank: int | None = None,
) -> Place:
    return Place(
        source_type=source_type,
        source_id=place_id,
        restaurant_id=place_id if source_type == "restaurant" else None,
        name=f"장소 {place_id}",
        category="한식" if source_type == "restaurant" else "전시",
        score=1.0,
        reason="검색 근거",
        rank=rank,
        selection_reason=f"{place_id} 선정 이유",
        address="서울시 중구",
        rating=4.56,
        review_count=1824,
        image="https://example.com/image.jpg",
        lat=37.56,
        lng=126.98,
    )


class FrontendResponseTests(unittest.TestCase):
    def test_single_recommendation_uses_recommend_list_only_and_limits_three(self):
        result = recommendation_frontend_response([
            place("4", rank=4),
            place("2", rank=2),
            place("1", rank=1),
            place("3", rank=3),
        ])

        self.assertEqual(result.responseType, "recommendation")
        self.assertIsNone(result.travelPath)
        self.assertIsNone(result.day)
        self.assertIsNone(result.allDay)
        self.assertEqual([item.id for item in result.recommendList], ["1", "2", "3"])
        self.assertEqual(result.recommendList[0].rating, "4.6")
        self.assertEqual(result.recommendList[0].reviews, "1,824")
        self.assertEqual(result.recommendList[0].selectionReason, "1 선정 이유")

    def test_route_uses_travel_path_only_and_builds_time(self):
        days = [
            DayPlan(day=1, theme="첫날", slots=[TimeSlot(
                slot_id="d1-r1",
                date="2026-07-16",
                time="12:00",
                end_time="13:00",
                category="식당",
                place=place("r1"),
                alternatives=[place("r2"), place("r3")],
            )]),
            DayPlan(day=2, theme="둘째 날", slots=[TimeSlot(
                slot_id="d2-a1",
                date="2026-07-17",
                time="14:00",
                category="문화시설",
                place=place("a1", source_type="attraction"),
                alternatives=[
                    place("a2", source_type="attraction"),
                    place("a3", source_type="attraction"),
                ],
            )]),
        ]

        result = route_frontend_response(days)

        self.assertEqual(result.responseType, "route")
        self.assertEqual(result.day, 1)
        self.assertEqual(result.allDay, 2)
        self.assertIsNone(result.recommendList)
        self.assertEqual(list(result.travelPath), ["1", "2"])
        self.assertEqual(result.travelPath["1"][0].slotId, "d1-r1")
        self.assertEqual(result.travelPath["2"][0].slotId, "d2-a1")
        self.assertEqual(result.travelPath["1"][0].time, "12:00 - 13:00")
        self.assertEqual(
            [item.id for item in result.travelPath["1"][0].alternatives],
            ["r2", "r3"],
        )
        self.assertEqual(result.travelPath["2"][0].category, "관광지")
        self.assertEqual(
            [item.id for item in result.travelPath["2"][0].alternatives],
            ["a2", "a3"],
        )

    def test_route_rejects_all_day_mismatch(self):
        with self.assertRaises(ValidationError):
            FrontendResponse(
                responseType="route",
                day=1,
                allDay=3,
                travelPath={"1": [], "2": []},
                recommendList=None,
            )

    def test_multi_day_route_exposes_shared_accommodation_outside_travel_path(self):
        days = [
            DayPlan(day=1, theme="첫날", slots=[]),
            DayPlan(day=2, theme="둘째 날", slots=[]),
        ]
        hotel = place("hotel-1", source_type="accommodation")
        alternatives = [
            place("hotel-2", source_type="accommodation"),
            place("hotel-3", source_type="accommodation"),
        ]

        result = route_frontend_response(
            days,
            accommodation=hotel,
            accommodation_alternatives=alternatives,
        )

        self.assertEqual(result.accommodation.id, "hotel-1")
        self.assertEqual(result.accommodation.category, "숙소")
        self.assertEqual(
            [item.id for item in result.accommodation.alternatives],
            ["hotel-2", "hotel-3"],
        )
        self.assertEqual(result.travelPath, {"1": [], "2": []})

    def test_route_rejects_non_contiguous_days(self):
        with self.assertRaises(ValidationError):
            FrontendResponse(
                responseType="route",
                day=1,
                allDay=2,
                travelPath={"1": [], "3": []},
                recommendList=None,
            )

    def test_recommendation_rejects_travel_path(self):
        with self.assertRaises(ValidationError):
            FrontendResponse(
                responseType="recommendation",
                day=None,
                allDay=None,
                travelPath={"1": []},
                recommendList=[],
            )

    def test_weather_has_no_place_payload(self):
        result = empty_frontend_response("weather")
        self.assertIsNone(result.travelPath)
        self.assertIsNone(result.recommendList)

    def test_untrusted_blank_and_invalid_detail_values_become_null(self):
        invalid = place("bad", rank=1)
        invalid.address = "   "
        invalid.image = ""
        invalid.rating = float("nan")
        invalid.review_count = -1
        invalid.lat = 999
        invalid.lng = float("inf")

        item = recommendation_frontend_response([invalid]).recommendList[0]

        self.assertIsNone(item.address)
        self.assertIsNone(item.image)
        self.assertIsNone(item.rating)
        self.assertIsNone(item.reviews)
        self.assertIsNone(item.lat)
        self.assertIsNone(item.lng)


if __name__ == "__main__":
    unittest.main()
