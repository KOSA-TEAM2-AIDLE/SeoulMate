"""관광지·리뷰 Vector 순위와 명시적 조건을 결합한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domains.attraction.constraint_evaluator import ConstraintAssessment, evaluate_constraints
from domains.attraction.repository import AttractionRecord, AttractionRetrievalResult, ReviewVectorHit
from domains.attraction.search_plan import AttractionSearchPlan
from services.location import haversine_km


RRF_K = 60
PROFILE_WEIGHT = 1.5
REVIEW_WEIGHT = 1.0
CATEGORY_BOOST = 0.02
# 사용자가 반경을 명시하면 그 값을 우선하며, 명시하지 않은 현재 위치 검색만 과도하게 넓어지는 것을 막는다.
DEFAULT_RADIUS_KM = 2.0


@dataclass(frozen=True)
class RankedAttractionCandidate:
    attraction: AttractionRecord
    score: float
    profile_rank: int | None
    profile_similarity: float | None
    review_hits: tuple[ReviewVectorHit, ...]
    profile_rrf_score: float
    review_rrf_score: float
    category_boost: float
    distance_km: float | None
    constraint_assessments: tuple[ConstraintAssessment, ...]


def _target_matches(record: AttractionRecord, query: str) -> bool:
    normalized = query.casefold()
    if any(term in normalized for term in ("고궁", "궁궐", "palace", "palaces")):
        return "고궁" in record.category or "palace" in record.category.casefold()
    return True


class AttractionReranker:
    implemented = True

    def rerank(self, retrieval: AttractionRetrievalResult, *, plan: AttractionSearchPlan, required_features: list[str], excluded_features: list[str], min_rating: float | None, as_of: date, limit: int) -> list[RankedAttractionCandidate]:
        profile_hits = {hit.attraction_id: hit for hit in retrieval.profile_hits}
        ids = set(profile_hits) | set(retrieval.review_hits_by_place)
        ranked: list[RankedAttractionCandidate] = []
        for attraction_id in ids:
            record = retrieval.attractions.get(attraction_id)
            if record is None:
                continue
            if record.kind == "event" and record.end_date is not None and record.end_date < as_of: # 종료된 행사 점검
                continue
            if plan.event_only and record.kind != "event": # 이벤트 타입만 추천이 들어왔는데, 후보의 이벤트가 행사가 아닌경우 .. 
                continue
            if plan.secondary_categories and record.category_secondary not in plan.secondary_categories: # 파싱된 결과 세컨더리 카테고리가 있으면서 선택된 카테고리가 있는데 파싱된 세컨더리 카테고리와 다르면
                continue
            if not plan.secondary_categories and plan.primary_categories and record.category_primary not in plan.primary_categories:
                continue
            if not _target_matches(record, plan.query_text):
                continue
            assessments = evaluate_constraints(
                record,
                required_features=required_features,
                excluded_features=excluded_features,
            )
            if any(item.status == "conflict" for item in assessments):
                continue
            if min_rating is not None and (record.rating is None or record.rating < min_rating):
                continue

            distance = None
            if plan.latitude is not None and plan.longitude is not None:
                if record.latitude is None or record.longitude is None:
                    continue
                distance = haversine_km(plan.latitude, plan.longitude, record.latitude, record.longitude)
                if distance > (plan.radius_km or DEFAULT_RADIUS_KM):
                    continue

            profile = profile_hits.get(attraction_id)
            profile_score = (
                PROFILE_WEIGHT / (RRF_K + profile.rank)
                if profile
                else 0.0
            )

            reviews = retrieval.review_hits_by_place.get(attraction_id, ())

            # 리뷰 수가 많은 장소가 단순히 리뷰 개수만으로 유리해지지 않도록
            # 리뷰별 RRF 점수의 평균만 보조 점수로 사용한다.
            review_score = (
                REVIEW_WEIGHT
                * sum(1 / (RRF_K + hit.rank) for hit in reviews)
                / len(reviews)
                if reviews
                else 0.0
            )

            category_score = (
                CATEGORY_BOOST
                if (plan.primary_categories or plan.secondary_categories)
                else 0.0
            )

            score = profile_score + review_score + category_score

            ranked.append(
                RankedAttractionCandidate(
                    record,
                    score,
                    profile.rank if profile else None,
                    profile.similarity if profile else None,
                    reviews,
                    profile_score,
                    review_score,
                    category_score,
                    distance,
                    assessments,
                )
            )
        ranked.sort(key=lambda item: (item.score, item.attraction.rating or -1, item.attraction.review_count), reverse=True)
        return ranked[:limit]


__all__ = ["AttractionReranker", "RankedAttractionCandidate"]
