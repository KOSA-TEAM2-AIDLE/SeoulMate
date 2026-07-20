import unittest
from types import SimpleNamespace

from domains.cafe.repository import (
    CafeRecord,
    CafeRetrievalResult,
    CafeVectorHit,
    ReviewVectorHit,
)
from domains.cafe.search_service import (
    CafeSearchService,
    build_cafe_semantic_query,
    extract_cafe_category_hint,
)
from domains.common.models import DomainSearchRequest


class RecordingRepository:
    def __init__(self, retrieval: CafeRetrievalResult) -> None:
        self.retrieval = retrieval
        self.calls: list[tuple[str, str]] = []
        self.supporting_calls: list[tuple[tuple[float, ...], list[int], str]] = []

    def retrieve(self, query: str, *, language: str, **_options):
        self.calls.append((query, language))
        return self.retrieval

    def fetch_supporting_reviews(
        self,
        vector,
        cafe_ids,
        *,
        language,
        per_cafe=3,
    ):
        self.supporting_calls.append((tuple(vector), list(cafe_ids), language))
        return {
            10: (
                ReviewVectorHit(
                    review_id=100,
                    cafe_id=10,
                    content="조용하고 빵이 맛있어요",
                    rank=1,
                    similarity=0.95,
                    word_count=4,
                ),
            )
        }


class RecordingReranker:
    def rerank(self, retrieval, **options):
        self.options = options
        return []


def retrieval() -> CafeRetrievalResult:
    cafe = CafeRecord(
        id=10,
        name="성수 베이커리",
        category="베이커리 카페",
        rating=4.8,
        review_count=120,
        address="서울 성동구 성수동",
        phone=None,
        postal_code=None,
        hours="09:00-22:00",
        description="조용한 베이커리",
        image="cafe.jpg",
        link="https://example.com/cafe",
        lat=37.5445,
        lng=127.0560,
    )
    return CafeRetrievalResult(
        query="조용한 베이커리",
        language="ko",
        cafe_hits=(CafeVectorHit(cafe_id=10, rank=1, similarity=0.9),),
        review_hits_by_cafe={},
        cafes={10: cafe},
        query_vector=(0.1, 0.2),
    )


class CafeSearchServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_semantic_query_removes_location_and_generic_domain_name(self):
        request = DomainSearchRequest(
            task_id="cafe-1",
            domain="cafe",
            language="ko",
            search_query="성수 조용한 카페",
            themes=["작업하기 좋은"],
            location="성수",
        )

        self.assertEqual(
            "조용한 작업하기 좋은",
            build_cafe_semantic_query(request),
        )

    def test_category_hint_is_extracted_from_query_or_theme(self):
        request = DomainSearchRequest(
            task_id="cafe-1",
            domain="cafe",
            search_query="분위기 좋은 카페",
            themes=["디저트가 맛있는"],
        )

        self.assertEqual("디저트", extract_cafe_category_hint(request))

    async def test_search_geocodes_target_and_returns_common_candidates(self):
        repository = RecordingRepository(retrieval())
        service = CafeSearchService(
            repository=repository,
            geocoder=lambda location: (37.5444, 127.0558, location),
        )
        request = DomainSearchRequest(
            task_id="cafe-1",
            domain="cafe",
            language="ko",
            search_query="성수 조용한 베이커리 카페",
            themes=["조용한"],
            location="성수",
            current_location_name="홍대",
            min_rating=4.5,
            candidate_count=3,
        )

        candidates = await service.search(request)

        self.assertEqual([("조용한 베이커리", "ko")], repository.calls)
        self.assertEqual(1, len(candidates))
        self.assertEqual("cafe", candidates[0].domain)
        self.assertEqual("10", candidates[0].place_id)
        self.assertEqual(
            ["조용하고 빵이 맛있어요"],
            candidates[0].evidence,
        )
        self.assertEqual(
            [((0.1, 0.2), [10], "ko")],
            repository.supporting_calls,
        )
        self.assertLess(candidates[0].signals["distance_km"], 1)
        self.assertGreater(candidates[0].signals["category_boost"], 0)

    async def test_route_search_uses_broader_default_pool_for_neighbor_reranking(self):
        reranker = RecordingReranker()
        service = CafeSearchService(
            repository=RecordingRepository(retrieval()),
            reranker=reranker,
            geocoder=lambda location: (37.5444, 127.0558, location),
        )
        request = DomainSearchRequest(
            task_id="cafe-1",
            domain="cafe",
            search_query="성수 카페",
            location="성수",
            context={
                "parsed_query": SimpleNamespace(intent="multi_day_route"),
            },
        )

        await service.search(request)

        self.assertEqual(5.0, reranker.options["radius_km"])

    async def test_same_current_location_reuses_coordinates_without_geocoding(self):
        repository = RecordingRepository(retrieval())

        def unexpected_geocode(location):
            raise AssertionError(f"unexpected geocode: {location}")

        service = CafeSearchService(
            repository=repository,
            geocoder=unexpected_geocode,
        )
        request = DomainSearchRequest(
            task_id="cafe-1",
            domain="cafe",
            search_query="성수 카페",
            location="성수",
            latitude=37.5444,
            longitude=127.0558,
            current_location_name="성수",
        )

        candidates = await service.search(request)

        self.assertEqual(1, len(candidates))

    async def test_current_location_alias_reuses_coordinates_without_geocoding(self):
        repository = RecordingRepository(retrieval())

        def unexpected_geocode(location):
            raise AssertionError(f"unexpected geocode: {location}")

        service = CafeSearchService(
            repository=repository,
            geocoder=unexpected_geocode,
        )
        request = DomainSearchRequest(
            task_id="cafe-1",
            domain="cafe",
            search_query="현재 위치 분위기 좋은 카페",
            location="현재 위치",
            latitude=37.5444,
            longitude=127.0558,
        )

        candidates = await service.search(request)

        self.assertEqual(1, len(candidates))
        self.assertLess(candidates[0].signals["distance_km"], 1)

    async def test_implicit_nearby_radius_expands_when_two_km_has_no_results(self):
        repository = RecordingRepository(retrieval())
        service = CafeSearchService(repository=repository)
        request = DomainSearchRequest(
            task_id="cafe-en-1",
            domain="cafe",
            language="en",
            search_query="Recommend a cafe near my location",
            location="my location",
            latitude=37.5245,
            longitude=127.0560,
        )

        candidates = await service.search(request)

        self.assertEqual(1, len(candidates))
        self.assertGreater(candidates[0].signals["distance_km"], 2)
        self.assertLess(candidates[0].signals["distance_km"], 5)

    async def test_explicit_radius_is_not_automatically_expanded(self):
        repository = RecordingRepository(retrieval())
        service = CafeSearchService(repository=repository)
        request = DomainSearchRequest(
            task_id="cafe-en-1",
            domain="cafe",
            language="en",
            search_query="Recommend a cafe within two kilometers",
            location="my location",
            latitude=37.5245,
            longitude=127.0560,
            radius_km=2.0,
        )

        candidates = await service.search(request)

        self.assertEqual([], candidates)

    async def test_explicit_radius_without_resolved_coordinates_fails(self):
        service = CafeSearchService(
            repository=RecordingRepository(retrieval()),
            geocoder=lambda location: None,
        )
        request = DomainSearchRequest(
            task_id="cafe-1",
            domain="cafe",
            search_query="성수 카페",
            location="성수",
            radius_km=1.0,
        )

        with self.assertRaisesRegex(ValueError, "목적지 좌표"):
            await service.search(request)

    async def test_wrong_domain_is_rejected(self):
        service = CafeSearchService(
            repository=RecordingRepository(retrieval()),
        )
        request = DomainSearchRequest(
            task_id="restaurant-1",
            domain="restaurant",
            search_query="식당",
        )

        with self.assertRaisesRegex(ValueError, "restaurant"):
            await service.search(request)


if __name__ == "__main__":
    unittest.main()
