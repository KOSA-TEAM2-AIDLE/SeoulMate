"""전용 선택기가 있는 도메인만 등록하는 후보 선택 Registry."""

from __future__ import annotations

from application.recommendation.selection_interface import (
    DomainCandidateSelectionService,
)


class DomainSelectionRegistry:
    def __init__(
        self,
        services: list[DomainCandidateSelectionService] | None = None,
    ) -> None:
        self._services: dict[str, DomainCandidateSelectionService] = {}
        for service in services or []:
            self.register(service)

    def register(
        self,
        service: DomainCandidateSelectionService,
        *,
        replace: bool = False,
    ) -> None:
        domain = service.domain.strip().lower()
        if not domain:
            raise ValueError("선택 서비스의 domain은 비어 있을 수 없습니다.")
        if domain in self._services and not replace:
            raise ValueError(f"이미 등록된 선택 서비스입니다: {domain}")
        self._services[domain] = service

    def get_optional(
        self,
        domain: str,
    ) -> DomainCandidateSelectionService | None:
        return self._services.get(domain.strip().lower())

    def registered_domains(self) -> tuple[str, ...]:
        return tuple(sorted(self._services))


def build_default_selection_registry() -> DomainSelectionRegistry:
    from domains.attraction.selection_service import (
        AttractionSelectionService,
    )

    return DomainSelectionRegistry([AttractionSelectionService()])


__all__ = [
    "DomainSelectionRegistry",
    "build_default_selection_registry",
]
