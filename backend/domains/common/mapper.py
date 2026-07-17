"""공통 SearchCandidate를 채팅·루트 내부 Place로 변환한다."""

from __future__ import annotations

from typing import Any

from domains.common.models import SearchCandidate
from schemas.common import Place


def _number(value: Any, cast):
    if value is None:
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def search_candidate_to_place(
    candidate: SearchCandidate,
    *,
    rank: int | None = None,
    selection_reason: str | None = None,
) -> Place:
    """검색기가 검증한 값만 복사하며 GPT가 상세 정보를 만들지 못하게 한다."""

    attributes = candidate.attributes
    weather_reasons = list(candidate.signals.get("weather_reasons") or [])
    reason = (
        selection_reason
        or str(attributes.get("reason") or attributes.get("fallback_reason") or "").strip()
        or (candidate.evidence[0] if candidate.evidence else "검색 조건과의 관련도가 높은 후보입니다.")
    )
    return Place(
        source_type=candidate.domain,
        source_id=candidate.place_id,
        restaurant_id=candidate.place_id if candidate.domain == "restaurant" else None,
        task_id=candidate.task_id,
        name=candidate.name,
        category=candidate.category,
        score=float(candidate.final_score),
        # 관광 Context Enricher가 MCP 결과를 signals에 보관한다. 공통 Place에도
        # 전달해야 프론트가 다른 도메인과 동일하게 혼잡도 상태를 표시할 수 있다.
        congestion=candidate.signals.get("congestion_level"),
        reason=reason,
        rank=rank,
        selection_reason=selection_reason,
        address=attributes.get("address"),
        rating=_number(attributes.get("rating"), float),
        review_count=_number(
            attributes.get("review_count", attributes.get("reviews")), int
        ),
        image=attributes.get("image") or attributes.get("image_url"),
        lat=candidate.latitude,
        lng=candidate.longitude,
        rag_score=float(candidate.base_score),
        weather_score=_number(candidate.signals.get("weather_score"), float),
        weather_reasons=weather_reasons,
        price=attributes.get("price"),
        live_rating=attributes.get("live_rating"),
        link=attributes.get("url"),
        features=attributes.get("features"),
    )


__all__ = ["search_candidate_to_place"]
