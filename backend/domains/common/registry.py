"""도메인 조건문을 대체하는 검색기 Registry."""

from __future__ import annotations

from domains.common.exceptions import DomainNotRegisteredError
from domains.common.search_interface import DomainSearchService


class DomainSearchRegistry:
    def __init__(self) -> None:
        self._services: dict[str, DomainSearchService] = {}

    def register(self, service: DomainSearchService, *, replace: bool = False) -> None:
        domain = service.domain.strip().lower()
        if not domain:
            raise ValueError("검색기의 domain은 비어 있을 수 없습니다.")
        if domain in self._services and not replace:
            raise ValueError(f"이미 등록된 도메인입니다: {domain}")
        self._services[domain] = service

    def get(self, domain: str) -> DomainSearchService:
        normalized = domain.strip().lower()
        try:
            return self._services[normalized]
        except KeyError as exc:
            raise DomainNotRegisteredError(
                f"등록되지 않은 검색 도메인입니다: {normalized}"
            ) from exc

    def status(self) -> dict[str, bool]:
        return {
            domain: bool(getattr(service, "implemented", False))
            for domain, service in sorted(self._services.items())
        }


def build_default_domain_registry() -> DomainSearchRegistry:
    """식당은 실제 구현, 나머지는 팀 교체용 스켈레톤으로 등록한다."""
    from domains.accommodation.search_service import AccommodationSearchService
    from domains.attraction.search_service import AttractionSearchService
    from domains.cafe.search_service import CafeSearchService
    from domains.restaurant.search_service import RestaurantSearchService
    from domains.storage_locker.search_service import StorageLockerSearchService

    registry = DomainSearchRegistry()
    for service in (
        RestaurantSearchService(),
        CafeSearchService(),
        AccommodationSearchService(),
        AttractionSearchService(),
        StorageLockerSearchService(),
    ):
        registry.register(service)
    return registry


__all__ = ["DomainSearchRegistry", "build_default_domain_registry"]
