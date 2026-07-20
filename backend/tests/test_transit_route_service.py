import unittest

from schemas.transit import TransitPoint
from services.transit_route_service import build_lane_map_object, parse_transit_segment


class TransitRouteServiceTests(unittest.TestCase):
    def test_adds_default_coordinate_base_to_odsay_map_object(self) -> None:
        self.assertEqual("0:0@1071:1:24:34", build_lane_map_object("1071:1:24:34"))

    def test_parses_route_summary_from_odsay_info_object(self) -> None:
        segment = parse_transit_segment(
            TransitPoint(lat=37.5665, lng=126.978),
            TransitPoint(lat=37.4979, lng=127.0276),
            {
                "info": {
                    "totalTime": 40,
                    "payment": 1500,
                    "busTransitCount": 1,
                    "subwayTransitCount": 0,
                    "totalWalkTime": 10,
                    "mapObj": "1071:1:24:34",
                },
                "subPath": [{"trafficType": 2, "sectionTime": 30}],
            },
        )

        self.assertEqual(40, segment.duration_minutes)
        self.assertEqual(1500, segment.fare)
        self.assertEqual(0, segment.transfers)
        self.assertEqual(10, segment.walking_minutes)
        self.assertEqual("1071:1:24:34", segment.map_object)


if __name__ == "__main__":
    unittest.main()
