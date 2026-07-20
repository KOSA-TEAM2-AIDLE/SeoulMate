import unittest

from domains.accommodation.agent import apply_structured_location_intent


class AccommodationLocationTests(unittest.TestCase):
    def test_structured_district_overrides_city_hall_default(self):
        intent = {
            "location": "서울",
            "location_type": "default",
            "lat": 37.5665,
            "lng": 126.9780,
            "keyword": "서울",
        }

        resolved = apply_structured_location_intent(intent, "송파구")

        self.assertEqual("송파구", resolved["location"])
        self.assertEqual("district", resolved["location_type"])
        self.assertEqual("송파구", resolved["keyword"])
        self.assertAlmostEqual(37.5133, resolved["lat"])
        self.assertAlmostEqual(127.1002, resolved["lng"])

    def test_citywide_location_keeps_non_spatial_intent(self):
        intent = {
            "location": "서울",
            "location_type": "default",
            "lat": 37.5665,
            "lng": 126.9780,
        }

        self.assertIs(
            intent,
            apply_structured_location_intent(intent, "서울 전체"),
        )


if __name__ == "__main__":
    unittest.main()
