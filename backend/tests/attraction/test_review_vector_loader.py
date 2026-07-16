import json
import tempfile
import unittest
from pathlib import Path

from scripts.attraction.load_review_vectors import read_review_documents


class ReviewVectorLoaderTests(unittest.TestCase):
    def test_reads_review_jsonl_as_rag_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.jsonl"
            path.write_text(json.dumps({
                "document_id": "review:1:r1:en", "content": "Great", "metadata": {"kind": "review"}, "content_hash": "a" * 64,
            }) + "\n", encoding="utf-8")

            documents = read_review_documents(path)

        self.assertEqual("review:1:r1:en", documents[0].document_id)
