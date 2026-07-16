import unittest
from datetime import date

from scripts.attraction.prepare_review_targets import build_review_targets


class ReviewTargetTests(unittest.TestCase):
    def test_does_not_select_expired_event_for_review_collection(self):
        rows = [
            {
                "cid": "ENP000003",
                "lang_code_id": "en",
                "category_path": "Festivals/Events/Performances > Festivals",
                "name": "Expired festival",
                "road_address": "Seoul",
                "longitude": "126.9780",
                "latitude": "37.5665",
                "schedule_end_date": "2026-07-15",
            },
            {
                "cid": "ENP000004",
                "lang_code_id": "en",
                "category_path": "Culture > Parks",
                "name": "Active park",
                "road_address": "Seoul",
                "longitude": "126.9780",
                "latitude": "37.5665",
                "schedule_end_date": "",
            },
        ]

        targets = build_review_targets(rows, as_of=date(2026, 7, 16))

        self.assertEqual(["000004"], [target["place_key"] for target in targets])
