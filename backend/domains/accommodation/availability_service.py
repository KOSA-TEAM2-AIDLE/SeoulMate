from integrations.booking.client import BookingClient


class AccommodationAvailabilityService:
    """DB 상위 숙박 후보에만 Booking.com 가용성을 붙이는 스켈레톤."""

    implemented = False

    def __init__(self, client: BookingClient | None = None) -> None:
        self.client = client or BookingClient()

    async def enrich(self, candidates, request):
        raise NotImplementedError("Booking.com 계약 확정 후 상위 후보만 조회하세요.")

