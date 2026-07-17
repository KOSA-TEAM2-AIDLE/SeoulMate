"""관광 재랭킹 결과를 공통 SearchCandidate로 변환한다."""

from collections.abc import Sequence

from domains.attraction.repository import ReviewVectorHit
from domains.attraction.reranker import RankedAttractionCandidate
from domains.common.models import SearchCandidate


def to_search_candidate(
    ranked: RankedAttractionCandidate,
    task_id: str,
    *,
    supporting_reviews: Sequence[ReviewVectorHit] | None = None,
    original_question: str = "",
    required_features: Sequence[str] = (),
    excluded_features: Sequence[str] = (),
) -> SearchCandidate:
    place = ranked.attraction
    reviews = tuple(supporting_reviews) if supporting_reviews is not None else ranked.review_hits
    evidence = [hit.content for hit in reviews if hit.content]
    if not evidence:
        evidence.append(place.description or place.summary)
    return SearchCandidate(
        domain="attraction", place_id=place.id, task_id=task_id,
        name=place.name, category=place.category,
        latitude=place.latitude, longitude=place.longitude,
        base_score=ranked.score, final_score=ranked.score,
        evidence=evidence,
        attributes={
            "address": place.address, "kind": place.kind,
            "summary": place.summary, "description": place.description,
            "tags": place.tags, "hours": place.hours, "fee": place.fee,
            "image_url": place.image, "url": place.link,
            "rating": place.rating, "review_count": place.review_count,
            "english_review_count": place.english_review_count,
            "foreign_review_count": place.foreign_review_count,
            "start_date": place.start_date.isoformat() if place.start_date else None,
            "end_date": place.end_date.isoformat() if place.end_date else None,
            "distance_km": ranked.distance_km,
            "reason": evidence[0] if evidence else "검색 조건과 관련도가 높은 관광지입니다.",
        },
        signals={
            "profile_vector_rank": ranked.profile_rank,
            "profile_vector_similarity": ranked.profile_similarity,
            "review_vector_ranks": [hit.rank for hit in ranked.review_hits],
            "review_vector_similarities": [hit.similarity for hit in ranked.review_hits],
            "profile_rrf_score": ranked.profile_rrf_score,
            "review_rrf_score": ranked.review_rrf_score,
            "category_boost": ranked.category_boost,
            "distance_km": ranked.distance_km,
            "constraint_assessments": [
                {
                    "source_text": assessment.source_text,
                    "normalized_text": assessment.normalized_text,
                    "kind": assessment.kind,
                    "status": assessment.status,
                    "evidence": list(assessment.evidence),
                }
                for assessment in ranked.constraint_assessments
            ],
            "constraint_context": {
                "original_question": original_question,
                "required_features": list(required_features),
                "excluded_features": list(excluded_features),
            },
        },
    )


__all__ = ["to_search_candidate"]
