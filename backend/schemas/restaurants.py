"""API 명세서 5장 참고."""
from pydantic import BaseModel


class Restaurant(BaseModel):
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


class RestaurantReview(BaseModel):
    id: int
    restaurant_id: str
    content: str
