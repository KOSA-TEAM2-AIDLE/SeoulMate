"""도메인 전용 후보 선택 전략의 공통 인터페이스."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from application.recommendation.selection_models import (
    CandidateSelectionResult,
)
from domains.common.models import DomainSearchRequest, SearchCandidate


@runtime_checkable
class DomainCandidateSelectionService(Protocol):
    domain: str

    async def select(
        self,
        request: DomainSearchRequest,
        candidates: list[SearchCandidate],
    ) -> CandidateSelectionResult: ...


__all__ = ["DomainCandidateSelectionService"]
