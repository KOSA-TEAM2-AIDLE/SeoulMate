from domains.common.skeleton import SkeletonDomainSearchService


class AccommodationSearchService(SkeletonDomainSearchService):
    domain = "accommodation"
    owner_todo = "숙박 DB 검색 후 상위 후보에만 Booking 가용성을 확인하세요."


__all__ = ["AccommodationSearchService"]

