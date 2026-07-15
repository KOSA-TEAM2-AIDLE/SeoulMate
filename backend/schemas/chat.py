"""API 명세서 3-5 참고: /chat 요청/응답 및 route_day, route_multi용 스키마."""
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator

from schemas.common import Place, ToolResult
from schemas.frontend_response import FrontendResponse
from schemas.structured_query import StructuredTravelQuery


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    lang: str = "en"  # ko | en | ja
    history: list[ChatMessage] = Field(default_factory=list)
    lat: Optional[float] = None
    lng: Optional[float] = None
    location_name: Optional[str] = None
    min_rating: Optional[float] = None
    open_now: bool = False
    # 상위 LangGraph의 고정 TravelQuery.source_mode를 그대로 전달하면 별도 GPT 라우팅을 생략한다.
    source_mode: Optional[Literal["rag_only", "rag_mcp", "mcp_only"]] = None
    # 고정 TravelQuery.intent를 함께 전달하면 기존 규칙 기반 Intent 분류도 생략한다.
    parsed_intent: Optional[Literal[
        "multi_day_route",
        "day_trip_route",
        "single_place_recommendation",
        "weather_information",
        "general_response",
    ]] = None
    # 권장 입력: 고정 GPT가 반환한 JSON 전체. 있으면 RAG가 원문을 다시 파싱하지 않는다.
    parsed_query: Optional[StructuredTravelQuery] = None

    @model_validator(mode="after")
    def validate_structured_contract(self):
        if self.parsed_query is None:
            return self
        if self.parsed_intent and self.parsed_intent != self.parsed_query.intent:
            raise ValueError("parsed_intent와 parsed_query.intent가 일치해야 합니다.")
        if (
            self.source_mode
            and self.parsed_query.source_mode
            and self.source_mode != self.parsed_query.source_mode
        ):
            raise ValueError("source_mode와 parsed_query.source_mode가 일치해야 합니다.")
        return self


class TimeSlot(BaseModel):
    slot_id: Optional[str] = None
    date: Optional[str] = None
    time: str
    end_date: Optional[str] = None
    end_time: Optional[str] = None
    category: str  # 관광지 | 식당 | 카페 | 숙박
    place: Place
    alternatives: list[Place] = Field(default_factory=list, max_length=2)


class DayPlan(BaseModel):
    day: int
    theme: str
    slots: list[TimeSlot]


Intent = Literal[
    "rag", "mcp", "both", "chitchat", "route_day", "route_multi"
]


class ChatMetaPlaces(BaseModel):
    """intent: rag | mcp | both | chitchat 일 때의 meta 이벤트 payload."""

    type: Literal["meta"] = "meta"
    intent: Intent
    places: list[Place] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    # SSE 프레임(type/intent/debug)과 화면 DTO를 분리한다. 프론트는 result만
    # 소비하고, places/reasons/sources는 디버깅에 계속 사용할 수 있다.
    result: Optional[FrontendResponse] = None


class ChatMetaRoute(BaseModel):
    """intent: route_day | route_multi 일 때의 meta 이벤트 payload."""

    type: Literal["meta"] = "meta"
    intent: Intent
    days: list[DayPlan]
    tool_results: list[ToolResult] = []
    total_days: int
    total_places: int
    route_id: Optional[str] = None
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
