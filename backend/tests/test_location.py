import unittest
from unittest.mock import patch

from services.location import (
    CITYWIDE_LOCATION_NAME,
    address_matches_search_area,
    extract_location,
    geocode_kakao,
    is_citywide_location,
    location_candidates,
    wants_citywide_search,
)


class LocationResolutionTests(unittest.TestCase):
    def test_address_district_rejects_coordinate_address_mismatch(self):
        self.assertFalse(
            address_matches_search_area("홍대", "서울 용산구 한강대로15길 23 1F")
        )
        self.assertTrue(
            address_matches_search_area("홍대", "서울 마포구 어울마당로 123")
        )
        # 매핑되지 않은 세부 동네는 기존 좌표 반경 판정에 맡긴다.
        self.assertTrue(
            address_matches_search_area("연희동", "서울 서대문구 연희로 21")
        )

    def test_citywide_location_variants_are_normalized(self):
        variants = (
            "서울", "서울 전체", "서울 전역", "서울 어디든", "서울 아무 데나",
            "아무 곳이나", "아무데나", "아무 지역이나", "어디든지",
            "어느 지역이든", "지역 상관없어요", "위치 무관", "지역 제한 없음",
            "Anywhere", "Any area", "No preference", "Seoul-wide",
        )
        for value in variants:
            with self.subTest(value=value):
                self.assertTrue(is_citywide_location(value))

        self.assertEqual(CITYWIDE_LOCATION_NAME, "서울 전체")
        self.assertFalse(is_citywide_location("서울시청"))
        self.assertFalse(is_citywide_location("홍대"))

    def test_free_text_citywide_detection_does_not_mistake_other_preferences(self):
        self.assertTrue(wants_citywide_search("서울이면 어디든 괜찮아"))
        self.assertTrue(wants_citywide_search("아무 데나 맛있는 곳으로 추천해줘"))
        self.assertFalse(wants_citywide_search("주차는 상관없어. 홍대 식당 추천"))
        self.assertTrue(wants_citywide_search(
            "상관없어요",
            location_clarification=True,
        ))
        self.assertFalse(wants_citywide_search("서울시청 근처 식당 추천"))

    @patch("services.location.KAKAO_REST_API_KEY", "configured-test-key")
    @patch("services.location._kakao_search")
    def test_administrative_neighborhood_falls_back_to_address_search(self, search):
        search.side_effect = [
            [{
                "place_name": "인천둘레길",
                "address_name": "인천 서해구 심곡동",
                "y": "37.5439",
                "x": "126.6819",
            }],
            [{
                "address_name": "서울 서대문구 연희동",
                "y": "37.5739100104158",
                "x": "126.935230751932",
            }],
        ]

        lat, lng, name = geocode_kakao("연희동")

        self.assertEqual(name, "서울 서대문구 연희동")
        self.assertAlmostEqual(lat, 37.5739100104158)
        self.assertAlmostEqual(lng, 126.935230751932)
        self.assertEqual(search.call_args_list[0].args, ("keyword", "연희동"))
        self.assertEqual(search.call_args_list[1].args, ("address", "서울 연희동"))

    def test_common_area_aliases_do_not_require_kakao_api(self):
        cases = {
            "홍대에서 조용한 식당": ("홍대입구역", "조용한 식당"),
            "성수동에서 데이트 식당": ("성수역", "데이트 식당"),
            "대학로에서 저녁 식사": ("혜화역", "저녁 식사"),
            "종로에서 한식당 추천": ("종각역", "한식당 추천"),
        }
        for query, (expected_name, expected_cleaned) in cases.items():
            with self.subTest(query=query), patch(
                "services.location.KAKAO_REST_API_KEY", ""
            ):
                name, lat, lng, cleaned = extract_location(query)
                self.assertEqual(name, expected_name)
                self.assertIsNotNone(lat)
                self.assertIsNotNone(lng)
                self.assertEqual(cleaned, expected_cleaned)

    def test_location_particles_are_removed_without_damaging_area_name(self):
        self.assertIn("성수동", location_candidates("성수동에서 식당 추천"))
        self.assertIn("대학로", location_candidates("대학로에서 식당 추천"))
        self.assertNotIn("대학", location_candidates("대학로에서 식당 추천"))

    def test_ambiguous_jongno_uses_stable_area_center(self):
        lat, lng, name = geocode_kakao("종로")
        self.assertEqual(name, "종각역")
        self.assertAlmostEqual(lat, 37.5702)
        self.assertAlmostEqual(lng, 126.9831)


if __name__ == "__main__":
    unittest.main()
