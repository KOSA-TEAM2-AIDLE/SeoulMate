"""API 명세서 6장 참고."""
from pydantic import BaseModel


class Accommodation(BaseModel):
    id: str
    name: str
    link: str
    review_count: int
    image: str
    road_address: str
    lat: float
    lng: float
    rating: float
    style: str  # 럭셔리 | 호스텔 | 게스트하우스 | 비즈니스
    languages: str  # 콤마 구분


class AccommodationReview(BaseModel):
    id: int
    accommodation_id: str
    content: str
