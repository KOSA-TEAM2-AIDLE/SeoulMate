"""카페 재랭킹 결과를 공통 SearchCandidate 계약으로 변환한다."""

from __future__ import annotations

from domains.cafe.reranker import RankedCafeCandidate
from domains.common.models import SearchCandidate


def to_search_candidate(
    ranked: RankedCafeCandidate,
    task_id: str,
) -> SearchCandidate:
    cafe = ranked.cafe
    evidence = [
        hit.content
        for hit in ranked.review_hits
        if hit.content
    ]
    if not evidence and cafe.description:
        evidence.append(cafe.description)

    return SearchCandidate(
        domain="cafe",
        place_id=str(cafe.id),
        task_id=task_id,
        name=cafe.name,
        category=cafe.category or "카페",
        latitude=cafe.lat,
        longitude=cafe.lng,
        base_score=ranked.score,
        final_score=ranked.score,
        evidence=evidence,
        attributes={
            "address": cafe.address,
            "phone": cafe.phone,
            "postal_code": cafe.postal_code,
            "hours": cafe.hours,
            "description": cafe.description,
            "image_url": cafe.image,
            "link": cafe.link,
            "rating": cafe.rating,
            "review_count": cafe.review_count,
            "reason": (
                evidence[0]
                if evidence
                else "카페 정보와 요청 조건의 관련도가 높은 후보입니다."
            ),
        },
        signals={
            "cafe_vector_rank": ranked.cafe_vector_rank,
            "cafe_vector_similarity": ranked.cafe_vector_similarity,
            "review_vector_ranks": [
                hit.rank for hit in ranked.review_hits
            ],
            "review_vector_similarities": [
                hit.similarity for hit in ranked.review_hits
            ],
            "cafe_rrf_score": ranked.cafe_rrf_score,
            "review_rrf_score": ranked.review_rrf_score,
            "category_boost": ranked.category_boost,
            "distance_km": ranked.distance_km,
        },
    )


__all__ = ["to_search_candidate"]
