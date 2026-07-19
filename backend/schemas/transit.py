from pydantic import BaseModel, Field


class TransitPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class TransitSegment(BaseModel):
    origin: TransitPoint
    destination: TransitPoint
    duration_minutes: int | None = None
    fare: int | None = None
    transfers: int | None = None
    walking_minutes: int | None = None
    steps: list[dict] = []
    map_object: str | None = None
