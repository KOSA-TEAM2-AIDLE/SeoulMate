"""Registry 검색과 미구현 도메인 fallback을 한곳에서 처리한다."""

from __future__ import annotations

import psycopg2.errors
from pydantic import BaseModel, Field

from application.recommendation.request_factory import build_domain_search_request
from domains.common.exceptions import (
    DomainNotImplementedError,
    DomainNotRegisteredError,
)
from domains.common.models import SearchCandidate
from domains.common.registry import DomainSearchRegistry
from schemas.structured_query import StructuredQueryTask, StructuredTravelQuery
from services.domain_agents import mock_places_for_task


class DomainSearchBatch(BaseModel):
    task_id: str
    domain: str
    candidates: list[SearchCandidate]
    source_kind: str
    sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def used_mock(self) -> bool:
        return self.source_kind == "mock"


def _mock_candidates(
    task: StructuredQueryTask,
    *,
    latitude: float | None,
    longitude: float | None,
    candidate_count: int,
) -> list[SearchCandidate]:
    places = mock_places_for_task(
        task,
        lat=latitude,
        lng=longitude,
        candidate_count=candidate_count,
    )
    return [
        SearchCandidate(
            domain=place.source_type,
            place_id=place.source_id,
            task_id=task.task_id,
            name=place.name,
            category=place.category,
            latitude=place.lat,
            longitude=place.lng,
            base_score=float(place.score),
            final_score=float(place.score),
            evidence=[place.reason],
            attributes={"reason": place.reason, "mock": True},
            signals={"source_kind": "mock"},
        )
        for place in places
    ]


async def execute_domain_search(
    registry: DomainSearchRegistry,
    parsed: StructuredTravelQuery,
    task: StructuredQueryTask,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    current_location_name: str | None = None,
    candidate_count: int = 10,
    min_rating: float | None = None,
) -> DomainSearchBatch:
    """실제 검색기를 우선 사용하고 미구현 예외에만 명시적 mock을 반환한다."""

    request = build_domain_search_request(
        parsed,
        task,
        latitude=latitude,
        longitude=longitude,
        current_location_name=current_location_name,
        candidate_count=candidate_count,
        min_rating=min_rating,
    )
    # 아래 예외를 모두 mock 후보로 폴백한다. 이렇게 하면 단일 추천과 루트 모두에서
    # 빈 응답/하드 크래시 대신 안전한 임시 후보가 나온다.
    #  - DomainNotRegisteredError: 미등록 도메인(예: 파서가 내보내는 'etc')
    #  - DomainNotImplementedError: 스켈레톤(미구현) 도메인
    #  - UndefinedTable: 검색기는 구현됐지만 테이블이 아직 적재되지 않은 도메인
    #    (예: 카페 데이터 미적재). 데이터가 들어오면 자동으로 실제 결과로 전환된다.
    try:
        service = registry.get(task.domain)
        candidates = await service.search(request)
    except (
        DomainNotImplementedError,
        DomainNotRegisteredError,
        psycopg2.errors.UndefinedTable,
    ) as exc:
        return DomainSearchBatch(
            task_id=task.task_id,
            domain=task.domain,
            candidates=_mock_candidates(
                task,
                latitude=latitude,
                longitude=longitude,
                candidate_count=candidate_count,
            ),
            source_kind="mock",
            sources=[f"mock-{task.domain}-agent"],
            warnings=[str(exc)],
        )

    invalid = [candidate for candidate in candidates if candidate.domain != task.domain]
    if invalid:
        raise ValueError(f"{task.domain} 검색기가 다른 도메인의 후보를 반환했습니다.")
    ordered = sorted(candidates, key=lambda item: item.final_score, reverse=True)
    suffix = "en" if parsed.language == "en" else "ko"
    sources = (
        [f"restaurant_{suffix}", f"restaurant_review_{suffix}", f"restaurant_menu_{suffix}"]
        if task.domain == "restaurant"
        else [f"{task.domain}-search-service"]
    )
    return DomainSearchBatch(
        task_id=task.task_id,
        domain=task.domain,
        candidates=ordered[:candidate_count],
        source_kind="live",
        sources=sources,
    )


__all__ = ["DomainSearchBatch", "execute_domain_search"]
