import unittest

from domains.attraction.search_service import should_geocode_location
from domains.common.models import DomainSearchRequest


class AttractionLocationPolicyTests(unittest.TestCase):
    def test_current_location_alias_keeps_frontend_coordinates(self):
        request = DomainSearchRequest(
            task_id="task_1",
            domain="attraction",
            search_query="현재 내 주변 산책 장소",
            location="현재 위치",
            latitude=37.5665,
            longitude=126.978,
        )

        self.assertFalse(should_geocode_location(request))

    def test_explicit_destination_is_geocoded_when_not_current_location(self):
        request = DomainSearchRequest(
            task_id="task_1",
            domain="attraction",
            search_query="경복궁 근처 관광지",
            location="경복궁",
            latitude=37.5665,
            longitude=126.978,
        )

        self.assertTrue(should_geocode_location(request))


if __name__ == "__main__":
    unittest.main()
