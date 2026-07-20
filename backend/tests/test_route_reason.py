"""네 도메인의 루트 추천 이유가 같은 문장 골격을 쓰는지 검증한다."""

import unittest

from application.recommendation.route_reason import (
    RouteReasonFacts,
    build_route_reason,
)


class RouteReasonKoreanTest(unittest.TestCase):
    def test_all_domains_share_one_sentence_skeleton(self):
        reasons = [
            build_route_reason(RouteReasonFacts(
                domain="restaurant",
                category="스시야",
                rating=4.5,
                review_count=320,
                open_at_visit_time=True,
                visit_time="12:30",
                distance_from_previous_km=0.8,
            )),
            build_route_reason(RouteReasonFacts(
                domain="cafe",
                category="디저트 카페",
                rating=4.3,
                review_count=118,
                distance_from_previous_km=0.52,
            )),
            build_route_reason(RouteReasonFacts(
                domain="attraction",
                category="고궁",
                rating=4.6,
                review_count=902,
                distance_from_previous_km=1.14,
            )),
            build_route_reason(RouteReasonFacts(
                domain="accommodation",
                category="호텔",
                rating=4.4,
                review_count=507,
                distance_from_area_km=1.2,
            )),
        ]
        for reason in reasons:
            self.assertTrue(reason.startswith("평점 "))
            self.assertIn("리뷰 ", reason)
            self.assertTrue(reason.endswith("입니다."))

    def test_domain_specific_clauses_are_included(self):
        restaurant = build_route_reason(RouteReasonFacts(
            domain="restaurant",
            category="스시야",
            rating=4.5,
            review_count=320,
            open_at_visit_time=True,
            visit_time="12:30",
            distance_from_previous_km=0.8,
        ))
        self.assertEqual(
            restaurant,
            "평점 4.5(리뷰 320개)의 스시야로, 12:30 방문 시간에 영업하며 "
            "직전 일정에서 800m 거리입니다.",
        )

        attraction = build_route_reason(RouteReasonFacts(
            domain="attraction",
            category="박물관",
            rating=4.6,
            review_count=902,
            weather_condition="rain",
            weather_indoor_evidence=True,
            distance_from_previous_km=1.14,
        ))
        self.assertIn("비·눈 예보에 맞는 실내 장소이며", attraction)
        self.assertTrue(attraction.endswith("직전 일정에서 1.1km 거리입니다."))

    def test_missing_facts_are_omitted_not_guessed(self):
        self.assertEqual(
            build_route_reason(RouteReasonFacts(domain="cafe")),
            "카페로, 요청 조건과 이동 동선을 함께 고려한 선택입니다.",
        )
        self.assertEqual(
            build_route_reason(RouteReasonFacts(
                domain="attraction", category="공원", is_first_stop=True
            )),
            "공원으로, 그날 일정의 첫 방문지입니다.",
        )
        self.assertEqual(
            build_route_reason(RouteReasonFacts(
                domain="restaurant",
                category="한식당",
                rating=4.2,
                distance_from_previous_km=0.3,
            )),
            "평점 4.2의 한식당으로, 직전 일정에서 300m 거리입니다.",
        )

    def test_sunny_forecast_does_not_claim_rain_wording(self):
        reason = build_route_reason(RouteReasonFacts(
            domain="attraction",
            category="미술관",
            rating=4.1,
            review_count=80,
            weather_condition="clear",
            weather_indoor_evidence=True,
            distance_from_previous_km=0.9,
        ))
        self.assertNotIn("비·눈", reason)

    def test_korean_particle_follows_final_consonant(self):
        self.assertTrue(build_route_reason(RouteReasonFacts(
            domain="attraction", category="공원", is_first_stop=True
        )).startswith("공원으로,"))
        self.assertTrue(build_route_reason(RouteReasonFacts(
            domain="cafe", category="카페", is_first_stop=True
        )).startswith("카페로,"))
        # ㄹ 받침은 '으로'가 아니라 '로'가 자연스럽다.
        self.assertTrue(build_route_reason(RouteReasonFacts(
            domain="accommodation", category="호텔", is_first_stop=True
        )).startswith("호텔로,"))


class RouteReasonEnglishTest(unittest.TestCase):
    def test_english_route_reason_uses_the_same_skeleton(self):
        restaurant = build_route_reason(
            RouteReasonFacts(
                domain="restaurant",
                category="sushi restaurant",
                rating=4.5,
                review_count=320,
                open_at_visit_time=True,
                visit_time="12:30",
                distance_from_previous_km=0.8,
            ),
            "en",
        )
        self.assertEqual(
            restaurant,
            "A sushi restaurant rated 4.5 (320 reviews), open at 12:30 "
            "and 800m from the previous stop.",
        )

        accommodation = build_route_reason(
            RouteReasonFacts(
                domain="accommodation",
                category="hotel",
                rating=4.4,
                review_count=507,
                distance_from_area_km=1.2,
            ),
            "en",
        )
        self.assertEqual(
            accommodation,
            "A hotel rated 4.4 (507 reviews), 1.2km from the itinerary area.",
        )

    def test_english_article_matches_leading_vowel(self):
        reason = build_route_reason(
            RouteReasonFacts(domain="attraction", category="art museum"),
            "en",
        )
        self.assertTrue(reason.startswith("An art museum,"))


if __name__ == "__main__":
    unittest.main()
