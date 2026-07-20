from pydantic import BaseModel


class Event(BaseModel):
    id: str
    lang_code: str  # KO | EN
    facility_name: str
    facility_summary: str
    facility_description: str
    place_name: str
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    image_url: str
    facility_tag: str  # 콤마 구분
    road_address: str
    lat: float
    lng: float
    subway_info: str
    hours: str
    has_fee: str  # Y | N
    fee: str
    homepage_url: str


class EventReview(BaseModel):
    id: int
    event_id: str
    content: str
