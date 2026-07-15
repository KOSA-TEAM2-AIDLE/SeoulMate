from domains.common.skeleton import SkeletonDomainSearchService


class StorageLockerSearchService(SkeletonDomainSearchService):
    domain = "storage_locker"
    owner_todo = "물품보관소 API client와 거리·운영시간·크기 필터를 연결하세요."


__all__ = ["StorageLockerSearchService"]

