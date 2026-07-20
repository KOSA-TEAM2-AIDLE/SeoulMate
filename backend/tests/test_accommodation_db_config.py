import unittest

from core.config import DB_CONFIG
from domains.accommodation.search_accommodation_rrf_en import DB_PARAMS
from domains.accommodation.vector_search import ACCOMMODATION_DB_CONFIG


class AccommodationDatabaseConfigTests(unittest.TestCase):
    def test_korean_search_uses_application_database(self) -> None:
        self.assertIs(DB_CONFIG, ACCOMMODATION_DB_CONFIG)

    def test_english_search_uses_application_database(self) -> None:
        self.assertIs(DB_CONFIG, DB_PARAMS)


if __name__ == "__main__":
    unittest.main()
