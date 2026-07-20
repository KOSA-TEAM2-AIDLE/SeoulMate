from typing import Literal

from pydantic import BaseModel, Field


class PoiMatch(BaseModel):
    area_code: str = Field(min_length=1)
    area_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    match_type: Literal["contains", "nearest"]
    distance_meters: float = Field(ge=0)

