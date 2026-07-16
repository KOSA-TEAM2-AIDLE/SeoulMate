import unittest
from datetime import date

from vector_db.attraction.repository import AttractionVectorRepository
from vector_db.attraction.schema import create_table_sql


class AttractionVectorSchemaTests(unittest.TestCase):
    def test_create_schema_uses_configured_embedding_dimension(self):
        sql = create_table_sql(1536)

        self.assertIn("attraction_vector_documents", sql)
        self.assertIn("vector(1536)", sql)
        self.assertIn("content_hash", sql)


class _RecordingCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows


class _RecordingConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_instance


class AttractionVectorRepositorySearchTests(unittest.TestCase):
    def test_search_profiles_filters_language_and_expired_events(self):
        cursor = _RecordingCursor([
            ("attraction:100:ko", "profile", {"place_key": "100", "kind": "attraction"}, 0.2),
        ])
        repository = AttractionVectorRepository(lambda: _RecordingConnection(cursor))

        rows = repository.search_profiles([0.1, 0.2], language="ko", as_of=date(2026, 7, 16), limit=5)

        self.assertEqual("attraction:100:ko", rows[0]["document_id"])
        sql, params = cursor.executed[0]
        self.assertIn("metadata->>'kind' IN ('attraction', 'event')", sql)
        self.assertIn("metadata->>'lang' = %s", sql)
        self.assertIn("metadata->>'end_date' = ''", sql)
        self.assertIn("metadata->>'end_date' >= %s", sql)
        self.assertEqual("ko", params[0])
        self.assertEqual("2026-07-16", params[1])
        self.assertEqual(5, params[-1])

    def test_search_reviews_limits_to_selected_places(self):
        cursor = _RecordingCursor([
            ("review:100:r1:ko", "review", "{\"place_key\": \"100\", \"kind\": \"review\"}", 0.1),
        ])
        repository = AttractionVectorRepository(lambda: _RecordingConnection(cursor))

        rows = repository.search_reviews([0.1, 0.2], language="ko", place_keys=["100", "200"], limit_per_place=3)

        self.assertEqual("100", rows[0]["metadata"]["place_key"])
        sql, params = cursor.executed[0]
        self.assertIn("metadata->>'kind' = 'review'", sql)
        self.assertIn("metadata->>'place_key' = ANY(%s)", sql)
        self.assertEqual("ko", params[0])
        self.assertEqual(["100", "200"], params[1])
        self.assertEqual(3, params[-1])
