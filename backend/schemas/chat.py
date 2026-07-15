from typing import Any, Literal, Optional, Self

from pydantic import BaseModel, Field, model_validator

from schemas.common import Place, ToolResult
from schemas.structured_query import (
    SourceMode,
    StructuredTravelQuery,
    TravelIntent,
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    lang: Literal["ko", "en"] = "ko"
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    location_name: str | None = None
    parsed_intent: TravelIntent
    source_mode: SourceMode | None = None
    parsed_query: StructuredTravelQuery
    route_modification: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat과 lng는 함께 제공해야 합니다.")
        if self.parsed_intent != self.parsed_query.intent:
            raise ValueError(
                "parsed_intent는 parsed_query.intent와 같아야 합니다."
            )
        if (
            self.source_mode is not None
            and self.parsed_query.source_mode is not None
            and self.source_mode != self.parsed_query.source_mode
        ):
            raise ValueError(
                "source_mode는 parsed_query.source_mode와 같아야 합니다."
            )
        if (
            self.route_modification is not None
            and self.parsed_intent != "modify_route"
        ):
            raise ValueError(
                "route_modification은 modify_route 요청에서만 사용할 수 있습니다."
            )
        return self


class TimeSlot(BaseModel):
    time: str
    category: str  # 관광지 | 식당 | 카페 | 숙박
    place: Place


class DayPlan(BaseModel):
    day: int
    theme: str
    slots: list[TimeSlot]


Intent = Literal[
    "rag", "mcp", "both", "chitchat", "route_day", "route_multi", "route_edit"
]


class ChatMetaPlaces(BaseModel):
    """intent: rag | mcp | both | chitchat 일 때의 meta 이벤트 payload."""

    type: Literal["meta"] = "meta"
    intent: Intent
    places: list[Place] = []
    tool_results: list[ToolResult] = []
    reasons: list[str] = []
    sources: list[str] = []


class ChatMetaRoute(BaseModel):
    """intent: route_day | route_multi | route_edit 일 때의 meta 이벤트 payload."""

    type: Literal["meta"] = "meta"
    intent: Intent
    days: list[DayPlan]
    tool_results: list[ToolResult] = []
    total_days: int
    total_places: int


class ChatToken(BaseModel):
    type: Literal["token"] = "token"
    text: str


class ChatDone(BaseModel):
    type: Literal["done"] = "done"


class ChatError(BaseModel):
    type: Literal["error"] = "error"
    message: str
