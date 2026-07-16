import unittest
from datetime import date

from domains.attraction.repository import AttractionRepository
from domains.attraction.search_service import AttractionSearchService
from domains.common.models import DomainSearchRequest
from vector_db.attraction.search import VectorSearchHit


class _FakeVectorSearch:
    def search(self, request):
        return [
            VectorSearchHit(
                document_id="attraction:ko-place:ko",
                place_key="ko-place",
                content="Name: 서울 미술관\nCategory: 문화시설\nAddress: 서울 중구 테스트로 1",
                metadata={
                    "lang": "ko", "kind": "attraction", "category": "문화시설",
                    "road_address": "서울 중구 테스트로 1", "latitude": 37.56,
                    "longitude": 126.98, "homepage_url": "https://example.com/ko",
                    "start_date": "", "end_date": "",
                },
                similarity=0.91,
                reviews=[],
            ),
            VectorSearchHit(
                document_id="attraction:en-place:en",
                place_key="en-place",
                content="Name: English Museum\nCategory: Museum",
                metadata={"lang": "en", "kind": "attraction", "category": "Museum"},
                similarity=0.99,
                reviews=[],
            ),
        ]


class AttractionSearchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_candidates_only_in_requested_language_with_verified_metadata(self):
        service = AttractionSearchService(
            repository=AttractionRepository(vector_search=_FakeVectorSearch())
        )
        request = DomainSearchRequest(
            task_id="attraction-1",
            domain="attraction",
            language="ko",
            search_query="미술관 추천",
            visit_date=date(2026, 7, 16),
        )

        candidates = await service.search(request)

        self.assertTrue(service.implemented)
        self.assertEqual(1, len(candidates))
        candidate = candidates[0]
        self.assertEqual("서울 미술관", candidate.name)
        self.assertEqual("ko-place", candidate.place_id)
        self.assertEqual("서울 중구 테스트로 1", candidate.attributes["address"])
        self.assertEqual("ko", candidate.attributes["language"])
        self.assertEqual([], candidate.evidence)

    async def test_rejects_other_domain_request(self):
        service = AttractionSearchService(
            repository=AttractionRepository(vector_search=_FakeVectorSearch())
        )
        request = DomainSearchRequest(task_id="wrong", domain="cafe", search_query="카페")

        with self.assertRaisesRegex(ValueError, "AttractionSearchService"):
            await service.search(request)
