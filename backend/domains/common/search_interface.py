"""팀별 검색기가 구현해야 하는 최소 Protocol."""

from typing import Protocol, runtime_checkable

from domains.common.models import DomainSearchRequest, SearchCandidate


@runtime_checkable
class DomainSearchService(Protocol):
    domain: str
    implemented: bool

    async def search(self, request: DomainSearchRequest) -> list[SearchCandidate]: ...


__all__ = ["DomainSearchService"]

