import tempfile
import unittest
from pathlib import Path

from vector_db.cafe.seed_vectordb import (
    CafeSeedFiles,
    clean_cafe_dataset,
    load_default_datasets,
)


class CafeVectorDbSeedTests(unittest.TestCase):
    def test_default_csvs_are_cleaned_with_expected_relationship_counts(self):
        default_files = CafeSeedFiles.from_directory(
            Path(__file__).parents[1] / "data" / "db_seed" / "cafe"
        )
        if not all(path.is_file() for path in default_files.paths):
            self.skipTest("기본 카페 CSV가 로컬에 없습니다.")
        ko, en = load_default_datasets()

        self.assertEqual((617, 2454), (len(ko.cafes), len(ko.reviews)))
        self.assertEqual(396, ko.report.invalid_cafes)
        self.assertEqual(2465, ko.report.orphan_reviews)
        self.assertEqual(189, ko.report.cafes_without_reviews)

        self.assertEqual((406, 607), (len(en.cafes), len(en.reviews)))
        self.assertEqual(11, en.report.invalid_cafes)
        self.assertEqual(85, en.report.orphan_reviews)
        self.assertEqual(3629, en.report.empty_reviews)
        self.assertEqual(275, en.report.cafes_without_reviews)

    def test_explicit_file_paths_are_reusable(self):
        files = CafeSeedFiles.from_directory(Path("custom/cafe-data"))

        self.assertEqual(Path("custom/cafe-data/ko_cafe.csv"), files.ko_cafe)
        self.assertEqual(Path("custom/cafe-data/en_cafe.csv"), files.en_cafe)

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
