import unittest
import tempfile
from pathlib import Path

from scripts.attraction.collect_visit_seoul import VisitSeoulClient
from scripts.data_pipeline.attraction.loader import read_visit_seoul_csv


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"contents": [{"cid": "KOP1"}]}


class FakeHttpClient:
    def __init__(self):
        self.request = None

    def get(self, url, *, headers, params, timeout):
        self.request = (url, headers, params, timeout)
        return FakeResponse()


class VisitSeoulCollectorTests(unittest.TestCase):
    def test_fetch_page_uses_api_key_header_and_returns_payload(self):
        http = FakeHttpClient()
        client = VisitSeoulClient("secret", http_client=http)

        payload = client.fetch_page("contents", {"langCode": "ko"})

        self.assertEqual([{"cid": "KOP1"}], payload["contents"])
        self.assertEqual("secret", http.request[1]["VISITSEOUL-API-KEY"])
        self.assertTrue(http.request[0].endswith("/contents"))

    def test_loader_accepts_large_unused_html_field(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.csv"
            path.write_text(
                "cid,lang_code_id,category_path,name,description_text,description_html\n"
                f"KOP1,ko,문화관광 > 공원,공원,설명,{'x' * 140000}\n",
                encoding="utf-8",
            )

            rows = read_visit_seoul_csv(path)

        self.assertEqual("KOP1", rows[0]["cid"])
