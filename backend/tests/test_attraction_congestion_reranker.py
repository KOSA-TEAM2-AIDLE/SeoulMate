import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from domains.attraction.congestion_reranker import (
    AttractionCongestionReranker,
)
from domains.attraction.context_enricher import AttractionContextEnricher
from domains.common.models import SearchCandidate
from domains.common.models import DomainSearchRequest
from integrations.mcp.base_client import ContextResult
from routers.chat import _rerank_attraction_candidates


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
    async def test_rag_only_still_enriches_attraction_congestion_context(self):
        enriched = _candidate().model_copy(update={
            "signals": {"congestion_available": True},
        })
        request = DomainSearchRequest(
            task_id="task_1",
            domain="attraction",
            search_query="현재 내 주변 추천",
            latitude=37.5796,
            longitude=126.977,
        )

        with patch(
            "routers.chat.attraction_context_enricher.enrich",
            new=AsyncMock(return_value=[enriched]),
        ) as enrich:
            result, sources = await _rerank_attraction_candidates(
                [_candidate()],
                SimpleNamespace(),
                "rag_only",
                request,
            )

        enrich.assert_awaited_once_with(request, [_candidate()])
        self.assertEqual([enriched], result)
        self.assertIn("Seoul-Congestion-MCP", sources)

    async def test_route_mode_skips_congestion_but_keeps_other_enrichment(self):
        class Congestion:
            async def rerank(self, candidates, question, *, language="ko"):
                raise AssertionError("루트 추천에서 혼잡도를 호출하면 안 됩니다.")

        class WeatherProvider:
            async def get_context(self, request):
                self.request = request
                return ContextResult(
                    provider="weather",
                    available=True,
                    data={"available": True, "condition": "clear"},
                )

        request = DomainSearchRequest(
            task_id="route-attraction-1",
            domain="attraction",
            search_query="강남구 관광지",
            location="강남구",
            latitude=37.5,
            longitude=127.0,
            visit_date=datetime.now(timezone.utc).date(),
            start_time="10:00",
        )
        enricher = AttractionContextEnricher(
            congestion_reranker=Congestion(),
            weather_provider=WeatherProvider(),
        )

        result = await enricher.enrich(
            request,
            [_candidate()],
            include_congestion=False,
        )

        self.assertNotIn("congestion_available", result[0].signals)
        self.assertTrue(result[0].signals["weather_available"])

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
        self.assertEqual(
            "서울시 실시간 도시데이터 권역",
            result[0].signals["congestion_basis"],
        )

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
