import unittest

from scripts.data_pipeline.attraction.reviews import build_review_documents, process_review_rows


class AttractionReviewTests(unittest.TestCase):
    def test_keeps_only_active_places_and_deduplicates_review_id(self):
        rows = [
            {"place_key": "000001", "review_id": "same", "crawl_status": "error", "original_text": "", "original_lang": "en", "rating": "3"},
            {"place_key": "000001", "review_id": "same", "crawl_status": "success", "original_text": "Great museum", "korean_text": "좋은 박물관", "original_lang": "en", "rating": "5"},
            {"place_key": "999999", "review_id": "gone", "crawl_status": "success", "original_text": "Old event", "original_lang": "en", "rating": "5"},
        ]

        result = process_review_rows(rows, active_place_keys={"000001"})

        self.assertEqual(1, len(result.reviews))
        self.assertEqual("Great museum", result.reviews[0]["original_text"])
        self.assertEqual(1, result.summary[0]["review_count"])

    def test_builds_korean_and_english_documents_using_language_policy(self):
        reviews = [{
            "place_key": "000001", "review_id": "r1", "rating": 5.0,
            "original_lang": "en", "original_text": "Great museum", "korean_text": "좋은 박물관",
        }]

        documents = build_review_documents(reviews, generated_on="2026-07-16")

        self.assertEqual({"review:000001:r1:ko", "review:000001:r1:en"}, {doc.document_id for doc in documents})
        self.assertEqual("좋은 박물관", next(doc.content for doc in documents if doc.metadata["lang"] == "ko"))
