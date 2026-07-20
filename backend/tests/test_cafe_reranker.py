import unittest

from domains.cafe.mapper import to_search_candidate
from domains.cafe.repository import (
    CafeRecord,
    CafeRetrievalResult,
    CafeVectorHit,
    ReviewVectorHit,
)
from domains.cafe.reranker import (
    CATEGORY_BOOST,
    CafeReranker,
    review_length_factor,
)


def cafe(
    cafe_id: int,
    *,
    category: str = "카페",
    rating: float | None = 4.5,
    review_count: int = 10,
    lat: float = 37.5,
    lng: float = 127.0,
) -> CafeRecord:
    return CafeRecord(
        id=cafe_id,
        name=f"카페 {cafe_id}",
        category=category,
        rating=rating,
        review_count=review_count,
        address=f"서울 {cafe_id}",
        phone=None,
        postal_code=None,
        hours="09:00-22:00",
        description=f"카페 {cafe_id} 설명",
        image=f"{cafe_id}.jpg",
        link=f"https://example.com/{cafe_id}",
        lat=lat,
        lng=lng,
    )


def review(
    review_id: int,
    cafe_id: int,
    rank: int,
    content: str,
) -> ReviewVectorHit:
    return ReviewVectorHit(
        review_id=review_id,
        cafe_id=cafe_id,
        content=content,
        rank=rank,
        similarity=0.9,
        word_count=len(content.split()),
    )


class CafeRerankerTests(unittest.TestCase):
    def test_rrf_combines_cafe_and_multiple_review_paths(self):
        retrieval = CafeRetrievalResult(
            query="조용한 작업 카페",
            language="ko",
            cafe_hits=(
                CafeVectorHit(cafe_id=1, rank=1, similarity=0.9),
                CafeVectorHit(cafe_id=2, rank=2, similarity=0.8),
            ),
            review_hits_by_cafe={
                2: (
                    review(21, 2, 1, "조용하고 콘센트가 많아서 작업하기 좋아요"),
                    review(22, 2, 2, "좌석도 넓고 오래 머물기 편합니다"),
                ),
            },
            cafes={1: cafe(1), 2: cafe(2)},
        )

        ranked = CafeReranker().rerank(retrieval)

        self.assertEqual([2, 1], [item.cafe.id for item in ranked])
        self.assertGreater(ranked[0].review_rrf_score, 0)
        self.assertEqual(0, ranked[1].review_rrf_score)

    def test_rating_distance_and_category_conditions_are_applied(self):
        retrieval = CafeRetrievalResult(
            query="베이커리",
            language="ko",
            cafe_hits=(
                CafeVectorHit(cafe_id=1, rank=1, similarity=0.9),
                CafeVectorHit(cafe_id=2, rank=2, similarity=0.8),
                CafeVectorHit(cafe_id=3, rank=3, similarity=0.7),
            ),
            review_hits_by_cafe={},
            cafes={
                1: cafe(1, category="베이커리 카페", rating=4.8),
                2: cafe(2, category="카페", rating=3.9),
                3: cafe(
                    3,
                    category="베이커리",
                    rating=4.9,
                    lat=37.65,
                    lng=127.15,
                ),
            },
        )

        ranked = CafeReranker().rerank(
            retrieval,
            category_hint="베이커리",
            min_rating=4.5,
            origin_latitude=37.5,
            origin_longitude=127.0,
            radius_km=2.0,
        )

        self.assertEqual([1], [item.cafe.id for item in ranked])
        self.assertEqual(CATEGORY_BOOST, ranked[0].category_boost)
        self.assertIsNotNone(ranked[0].distance_km)

    def test_mapper_preserves_verified_fields_and_search_signals(self):
        retrieval = CafeRetrievalResult(
            query="조용한 카페",
            language="ko",
            cafe_hits=(CafeVectorHit(cafe_id=1, rank=2, similarity=0.88),),
            review_hits_by_cafe={
                1: (review(11, 1, 4, "조용하고 좌석이 편안합니다"),),
            },
            cafes={1: cafe(1, category="스페셜티 커피", rating=4.7)},
        )
        ranked = CafeReranker().rerank(retrieval)[0]

        candidate = to_search_candidate(ranked, "cafe-task")

        self.assertEqual("cafe", candidate.domain)
        self.assertEqual("1", candidate.place_id)
        self.assertEqual("cafe-task", candidate.task_id)
        self.assertEqual(4.7, candidate.attributes["rating"])
        self.assertEqual(
            ["조용하고 좌석이 편안합니다"],
            candidate.evidence,
        )
        self.assertEqual(2, candidate.signals["cafe_vector_rank"])
        self.assertEqual([4], candidate.signals["review_vector_ranks"])

    def test_short_review_factor_and_invalid_radius_are_explicit(self):
        self.assertEqual(0.3, review_length_factor(3))
        self.assertEqual(0.8, review_length_factor(4))
        self.assertEqual(1.0, review_length_factor(7))
        empty = CafeRetrievalResult(
            query="카페",
            language="ko",
            cafe_hits=(),
            review_hits_by_cafe={},
            cafes={},
        )
        with self.assertRaisesRegex(ValueError, "기준 좌표"):
            CafeReranker().rerank(empty, radius_km=2.0)


if __name__ == "__main__":
    unittest.main()
