"""외부 연동 공통 응답 import 경로."""
from integrations.booking.schemas import BookingAvailability
from integrations.mcp.base_client import ContextRequest, ContextResult
from integrations.storage_locker.schemas import StorageLockerRecord

__all__ = ["BookingAvailability", "ContextRequest", "ContextResult", "StorageLockerRecord"]

