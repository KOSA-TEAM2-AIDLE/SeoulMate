from domains.common.exceptions import DomainNotImplementedError
from integrations.booking.schemas import BookingAvailability


class BookingClient:
    implemented = False

    async def check_availability(self, **params) -> list[BookingAvailability]:
        raise DomainNotImplementedError(
            "Booking.com API가 아직 연결되지 않았습니다. timeout 시 status=unknown으로 처리하세요."
        )


__all__ = ["BookingClient"]

