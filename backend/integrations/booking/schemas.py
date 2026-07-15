from typing import Literal

from pydantic import BaseModel


class BookingAvailability(BaseModel):
    accommodation_id: str
    status: Literal["available", "unavailable", "unknown"] = "unknown"
    total_price_krw: int | None = None
    booking_url: str | None = None
    checked_at: str | None = None


__all__ = ["BookingAvailability"]

