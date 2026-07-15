from pydantic import BaseModel


class StorageLockerRecord(BaseModel):
    external_id: str
    name: str
    latitude: float
    longitude: float
    operating_hours: str | None = None
    supported_sizes: list[str] = []


__all__ = ["StorageLockerRecord"]

