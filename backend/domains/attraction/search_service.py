from domains.common.skeleton import SkeletonDomainSearchService


class AttractionSearchService(SkeletonDomainSearchService):
    domain = "attraction"
    owner_todo = "전시 기간·휴관일·운영시간·실내외 검색을 구현하세요."


__all__ = ["AttractionSearchService"]

