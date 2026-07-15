from domains.common.skeleton import SkeletonDomainSearchService


class CafeSearchService(SkeletonDomainSearchService):
    domain = "cafe"
    owner_todo = "조용함·분위기·좌석·콘센트·디저트 검색을 구현하세요."


__all__ = ["CafeSearchService"]

