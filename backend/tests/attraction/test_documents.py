import unittest
from datetime import date

from scripts.data_pipeline.attraction.documents import build_documents
from scripts.data_pipeline.attraction.models import ProcessedPlace


class AttractionDocumentTests(unittest.TestCase):
    def test_builds_language_specific_document_without_html(self):
        place = ProcessedPlace(
            place_key="000001",
            source_cid="KOP000001",
            lang="ko",
            kind="attraction",
            category="문화관광 > 공원",
            name="서울 공원",
            summary="도심 공원",
            description="산책하기 좋은 장소",
            road_address="서울특별시 중구",
            latitude=37.5665,
            longitude=126.9780,
            hours="24 hours",
            fee="무료",
            tags="산책,공원",
            homepage_url="https://example.com",
            start_date=None,
            end_date=None,
        )

        documents = build_documents([place], generated_on=date(2026, 7, 16))

        self.assertEqual("attraction:000001:ko", documents[0].document_id)
        self.assertIn("서울 공원", documents[0].content)
        self.assertNotIn("<div", documents[0].content)
        self.assertEqual("attraction", documents[0].metadata["kind"])
        self.assertEqual("2026-07-16", documents[0].metadata["generated_on"])
