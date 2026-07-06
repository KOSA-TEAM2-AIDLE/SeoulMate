"""API 명세서 4장 참고."""
from pydantic import BaseModel


class Cafe(BaseModel):
    id: str
    name: str
    phone: str
    address: str
    postal_code: str
    lat: float
    lng: float
    category: str
    hours: str
    description: str
    image: str
    link: str


class CafeReview(BaseModel):
    id: int
    cafe_id: str
    content: str
