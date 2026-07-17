import unittest
from datetime import datetime, timezone

from domains.attraction.congestion_reranker import (
    AttractionCongestionReranker,
)
from domains.common.models import SearchCandidate
from integrations.mcp.base_client import ContextResult


def _candidate() -> SearchCandidate:
    return SearchCandidate(
        domain="attraction",
        place_id="palace-1",
        task_id="task_1",
        name="경복궁",
        category="역사관광",
        latitude=37.5796,
        longitude=126.977,
        base_score=0.8,
        final_score=0.8,
    )


class AttractionCongestionRerankerTests(unittest.IsolatedAsyncioTestCase):
    async def test_candidate_coordinates_are_sent_and_fresh_congestion_is_applied(self):
        class Provider:
            async def get_context(self, request):
                self.request = request
                return ContextResult(
                    provider="congestion",
                    available=True,
                    data={
                        "congestion": {
                            "congestion_level": "여유",
                            "congestion_score": 10,
                            "observed_at": datetime.now(
                                timezone.utc
                            ).isoformat(),
                        }
                    },
                )

        provider = Provider()
        result = await AttractionCongestionReranker(provider).rerank(
            [_candidate()],
            "오늘 고즈넉한 관광지 추천",
        )

        self.assertEqual(37.5796, provider.request.latitude)
        self.assertEqual(126.977, provider.request.longitude)
        self.assertEqual("경복궁", provider.request.place_name)
        self.assertGreater(result[0].final_score, 0.8)
        self.assertTrue(result[0].signals["congestion_available"])
        self.assertEqual("여유", result[0].signals["congestion_level"])
        self.assertEqual(10, result[0].signals["congestion_score"])

    async def test_mcp_failure_preserves_candidate_and_score(self):
        class Provider:
            async def get_context(self, request):
                raise RuntimeError("MCP unavailable")

        result = await AttractionCongestionReranker(Provider()).rerank(
            [_candidate()],
            "경복궁 근처 관광지",
        )

        self.assertEqual("palace-1", result[0].place_id)
        self.assertEqual(0.8, result[0].final_score)
        self.assertFalse(result[0].signals["congestion_available"])
        self.assertIn("RuntimeError", result[0].signals["congestion_error"])


if __name__ == "__main__":
    unittest.main()
