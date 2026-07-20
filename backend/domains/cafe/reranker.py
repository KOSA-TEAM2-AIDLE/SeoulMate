"""카페·리뷰 벡터 순위를 결합하고 명시적 조건으로 후보를 좁힌다."""

from __future__ import annotations

from dataclasses import dataclass

from domains.cafe.repository import (
    CafeRecord,
    CafeRetrievalResult,
    ReviewVectorHit,
)
from services.location import haversine_km


RRF_K = 60
CAFE_VECTOR_WEIGHT = 0.7
REVIEW_VECTOR_WEIGHT = 2.0
CATEGORY_BOOST = 0.015


@dataclass(frozen=True)
class RankedCafeCandidate:
    cafe: CafeRecord
    score: float
    cafe_vector_rank: int | None
    cafe_vector_similarity: float | None
    review_hits: tuple[ReviewVectorHit, ...]
    cafe_rrf_score: float
    review_rrf_score: float
    category_boost: float
    distance_km: float | None


def review_length_factor(word_count: int) -> float:
    """짧고 일반적인 리뷰는 제외하지 않고 RRF 기여도만 낮춘다."""

    if word_count < 4:
        return 0.3
    if word_count < 7:
        return 0.8
    return 1.0


def _normalized_category(value: str | None) -> str:
    return " ".join(str(value or "").casefold().split())


def _category_matches(category: str | None, hint: str | None) -> bool:
    normalized_category = _normalized_category(category)
    normalized_hint = _normalized_category(hint)
    if not normalized_category or not normalized_hint:
        return False
    return (
        normalized_hint in normalized_category
        or normalized_category in normalized_hint
    )


class CafeReranker:
    """카페 설명과 리뷰 검색 순위를 RRF로 결합한다."""

    implemented = True

    def rerank(
        self,
        retrieval: CafeRetrievalResult,
        *,
        category_hint: str | None = None,
        min_rating: float | None = None,
        origin_latitude: float | None = None,
        origin_longitude: float | None = None,
        radius_km: float | None = None,
        limit: int = 20,
    ) -> list[RankedCafeCandidate]:
        if limit < 1:
            raise ValueError("카페 후보 반환 수는 1 이상이어야 합니다.")
        if min_rating is not None and not 0 <= min_rating <= 5:
            raise ValueError("최소 평점은 0 이상 5 이하여야 합니다.")
        if radius_km is not None and radius_km <= 0:
            raise ValueError("검색 반경은 0보다 커야 합니다.")
        if radius_km is not None and (
            origin_latitude is None or origin_longitude is None
        ):
            raise ValueError("검색 반경을 적용하려면 기준 좌표가 필요합니다.")

        cafe_hits = {hit.cafe_id: hit for hit in retrieval.cafe_hits}
        all_ids = set(cafe_hits) | set(retrieval.review_hits_by_cafe)
        ranked: list[RankedCafeCandidate] = []

        for cafe_id in all_ids:
            cafe = retrieval.cafes.get(cafe_id)
            if cafe is None:
                continue
            if min_rating is not None and (
                cafe.rating is None or cafe.rating < min_rating
            ):
                continue

            distance_km = None
            if origin_latitude is not None and origin_longitude is not None:
                distance_km = haversine_km(
                    origin_latitude,
                    origin_longitude,
                    cafe.lat,
                    cafe.lng,
                )
                if radius_km is not None and distance_km > radius_km:
                    continue

            cafe_hit = cafe_hits.get(cafe_id)
            cafe_score = (
                CAFE_VECTOR_WEIGHT / (RRF_K + cafe_hit.rank)
                if cafe_hit is not None
                else 0.0
            )
            review_hits = retrieval.review_hits_by_cafe.get(cafe_id, ())
            review_score = REVIEW_VECTOR_WEIGHT * sum(
                review_length_factor(hit.word_count) / (RRF_K + hit.rank)
                for hit in review_hits
            )
            category_score = (
                CATEGORY_BOOST
                if _category_matches(cafe.category, category_hint)
                else 0.0
            )
            ranked.append(
                RankedCafeCandidate(
                    cafe=cafe,
                    score=cafe_score + review_score + category_score,
                    cafe_vector_rank=cafe_hit.rank if cafe_hit else None,
                    cafe_vector_similarity=(
                        cafe_hit.similarity if cafe_hit else None
                    ),
                    review_hits=review_hits,
                    cafe_rrf_score=cafe_score,
                    review_rrf_score=review_score,
                    category_boost=category_score,
                    distance_km=distance_km,
                )
            )

        ranked.sort(
            key=lambda item: (
                item.score,
                item.cafe.rating if item.cafe.rating is not None else -1,
                item.cafe.review_count,
                -item.cafe.id,
            ),
            reverse=True,
        )
        return ranked[:limit]


__all__ = [
    "CafeReranker",
    "RankedCafeCandidate",
    "review_length_factor",
]
