"""API 명세서 3-5 참고: /chat 요청/응답 및 루트 응답 스키마."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from schemas.common import Place, ToolResult
from core.language import detect_input_language
from schemas.frontend_response import FrontendResponse
from schemas.structured_query import SourceMode, StructuredTravelQuery, TravelIntent


class ChatMessage(BaseModel):
    role: str
    content: str


class RouteModificationRequest(BaseModel):
    current_route: dict[str, Any]
    target_slot_id: str = Field(min_length=1)
    expected_version: int = Field(ge=0)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    lang: str = "en"
    history: list[ChatMessage] = Field(default_factory=list)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    location_name: str | None = None
    min_rating: float | None = None
    open_now: bool = False
    source_mode: SourceMode | None = None
    parsed_intent: TravelIntent | None = None
    parsed_query: StructuredTravelQuery | None = None
    travel_query_thread_id: str | None = None
    route_modification: RouteModificationRequest | None = None

    @model_validator(mode="after")
    def validate_structured_contract(self):
        self.lang = detect_input_language(self.message, fallback=self.lang)
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat과 lng는 함께 제공해야 합니다.")
        if self.parsed_query is not None:
            if self.parsed_intent and self.parsed_intent != self.parsed_query.intent:
                raise ValueError("parsed_intent와 parsed_query.intent가 일치해야 합니다.")
            if (
                self.source_mode
                and self.parsed_query.source_mode
                and self.source_mode != self.parsed_query.source_mode
            ):
                raise ValueError("source_mode와 parsed_query.source_mode가 일치해야 합니다.")
        if (
            self.route_modification is not None
            and self.parsed_intent != "modify_route"
        ):
            raise ValueError(
                "route_modification은 modify_route 요청에서만 사용할 수 있습니다."
            )
        return self


class TimeSlot(BaseModel):
    slot_id: Optional[str] = None
    date: Optional[str] = None
    time: str
    end_date: Optional[str] = None
    end_time: Optional[str] = None
    category: str
    place: Place
    alternatives: list[Place] = Field(default_factory=list, max_length=2)


class DayPlan(BaseModel):
    day: int
    theme: str
    slots: list[TimeSlot]


Intent = Literal[
    "rag",
    "mcp",
    "both",
    "chitchat",
    "route_day",
    "route_multi",
]


class ChatMetaPlaces(BaseModel):
    type: Literal["meta"] = "meta"
    intent: Intent
    places: list[Place] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    continuation: dict[str, Any] | None = None
    result: Optional[FrontendResponse] = None


class ChatMetaRoute(BaseModel):
    type: Literal["meta"] = "meta"
    intent: Intent
    days: list[DayPlan]
    tool_results: list[ToolResult] = Field(default_factory=list)
    total_days: int
    total_places: int
    route_id: Optional[str] = None
    route_optimized: bool = False
    travel_distance_km: float | None = Field(default=None, ge=0)
    distance_method: Literal["haversine"] | None = None
    coordinate_coverage: float = Field(default=0.0, ge=0, le=1)
    result: Optional[FrontendResponse] = None


class ChatToken(BaseModel):
    type: Literal["token"] = "token"
    text: str


class ChatDone(BaseModel):
    type: Literal["done"] = "done"


class ChatError(BaseModel):
    type: Literal["error"] = "error"
    message: str
    result: Optional[FrontendResponse] = None
