"""미구현 팀 검색기의 공통 실패 동작."""

from domains.common.exceptions import DomainNotImplementedError
from domains.common.models import DomainSearchRequest, SearchCandidate


class SkeletonDomainSearchService:
    domain = ""
    implemented = False
    owner_todo = "팀 검색기를 구현하고 Registry 등록 객체를 교체하세요."

    async def search(self, request: DomainSearchRequest) -> list[SearchCandidate]:
        raise DomainNotImplementedError(f"{self.domain} 검색기가 아직 구현되지 않았습니다. {self.owner_todo}")


__all__ = ["SkeletonDomainSearchService"]

