import unittest
from datetime import date

from scripts.data_pipeline.attraction.transform import classify_and_filter_rows


class AttractionTransformTests(unittest.TestCase):
    def test_keeps_permanent_attraction_and_active_event(self):
        rows = [
            {
                "cid": "KOP000001",
                "lang_code_id": "ko",
                "category_path": "문화관광 > 공원",
                "name": "상시 공원",
                "description_text": "언제나 방문 가능한 공원",
                "longitude": "126.9780",
                "latitude": "37.5665",
                "schedule_start_date": "",
                "schedule_end_date": "",
            },
            {
                "cid": "KOP000002",
                "lang_code_id": "ko",
                "category_path": "축제/공연/행사 > 축제",
                "name": "진행 중 축제",
                "description_text": "주말 축제",
                "longitude": "126.9800",
                "latitude": "37.5700",
                "schedule_start_date": "2026-07-15",
                "schedule_end_date": "2026-07-20",
            },
        ]

        result = classify_and_filter_rows(rows, as_of=date(2026, 7, 16))

        self.assertEqual(["000001"], [row.place_key for row in result.attractions])
        self.assertEqual(["000002"], [row.place_key for row in result.events])
        self.assertEqual([], result.quarantine)

    def test_excludes_expired_event_but_keeps_undated_event(self):
        rows = [
            {
                "cid": "KOP000003",
                "lang_code_id": "ko",
                "category_path": "축제/공연/행사 > 축제",
                "name": "종료 축제",
                "description_text": "이미 끝난 행사",
                "schedule_end_date": "2026-07-15",
            },
            {
                "cid": "KOP000004",
                "lang_code_id": "ko",
                "category_path": "축제/공연/행사 > 공연",
                "name": "기간 미상 공연",
                "description_text": "날짜가 없다",
                "schedule_end_date": "",
            },
        ]

        result = classify_and_filter_rows(rows, as_of=date(2026, 7, 16))

        self.assertEqual(["000004"], [row.place_key for row in result.events])
        self.assertEqual({"expired_event"}, {row.reason for row in result.quarantine})
