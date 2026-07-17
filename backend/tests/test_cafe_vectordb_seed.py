import tempfile
import unittest
from pathlib import Path

from core.config import DATA_DIR
from vector_db.cafe.seed_vectordb import (
    clean_cafe_dataset,
    load_default_datasets,
)


class CafeVectorDbSeedTests(unittest.TestCase):
    def test_default_csvs_are_cleaned_with_expected_relationship_counts(self):
        ko, en = load_default_datasets(DATA_DIR)

        self.assertEqual((617, 2396), (len(ko.cafes), len(ko.reviews)))
        self.assertEqual(2403, ko.report.orphan_reviews)
        self.assertEqual(196, ko.report.cafes_without_reviews)

        self.assertEqual((559, 1672), (len(en.cafes), len(en.reviews)))
        self.assertEqual(726, en.report.orphan_reviews)
        self.assertEqual(174, en.report.empty_reviews)
        self.assertEqual(174, en.report.cafes_without_reviews)

    def test_rating_and_review_count_use_only_valid_matching_reviews(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cafe_path = root / "cafes.csv"
            review_path = root / "reviews.csv"
            cafe_path.write_text(
                "id,name,phone,address,postal_code,lat,lng,category,hours,"
                "description,image,link\n"
                "1,테스트 카페,,서울,,37.5,127.0,카페,,조용한 공간,,\n",
                encoding="utf-8",
            )
            review_path.write_text(
                "restaurant_id,rating,content\n"
                "1,5,조용하고 좋아요\n"
                "1,3,다시 방문하고 싶어요\n"
                "1,1,\n"
                "999,5,존재하지 않는 카페 리뷰\n",
                encoding="utf-8",
            )

            dataset = clean_cafe_dataset(cafe_path, review_path, "ko")

        self.assertEqual(2, dataset.cafes[0].review_count)
        self.assertEqual(4.0, dataset.cafes[0].rating)
        self.assertEqual(1, dataset.report.empty_reviews)
        self.assertEqual(1, dataset.report.orphan_reviews)
        self.assertIn("Address: 서울", dataset.cafes[0].embedding_content)

    def test_duplicate_cafe_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cafe_path = root / "cafes.csv"
            review_path = root / "reviews.csv"
            cafe_path.write_text(
                "id,name,phone,address,postal_code,lat,lng,category,hours,"
                "description,image,link\n"
                "1,A,,서울,,37.5,127.0,,,,,\n"
                "1,B,,서울,,37.6,127.1,,,,,\n",
                encoding="utf-8",
            )
            review_path.write_text(
                "restaurant_id,rating,content\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "중복 카페 ID"):
                clean_cafe_dataset(cafe_path, review_path, "ko")


if __name__ == "__main__":
    unittest.main()
