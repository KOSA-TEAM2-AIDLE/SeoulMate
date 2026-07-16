import unittest

from vector_db.attraction.schema import create_table_sql


class AttractionVectorSchemaTests(unittest.TestCase):
    def test_create_schema_uses_configured_embedding_dimension(self):
        sql = create_table_sql(1536)

        self.assertIn("attraction_vector_documents", sql)
        self.assertIn("vector(1536)", sql)
        self.assertIn("content_hash", sql)
