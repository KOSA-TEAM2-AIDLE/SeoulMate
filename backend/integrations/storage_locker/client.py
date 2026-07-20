from domains.common.exceptions import DomainNotImplementedError
from integrations.storage_locker.schemas import StorageLockerRecord


class StorageLockerClient:
    implemented = False

    async def search(self, **params) -> list[StorageLockerRecord]:
        raise DomainNotImplementedError("물품보관소 외부 API가 아직 연결되지 않았습니다.")


__all__ = ["StorageLockerClient"]

