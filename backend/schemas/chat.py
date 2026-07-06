"""API 명세서 3-5, 10장 참고: /chat 요청/응답 및 route_day, route_multi, route_edit용 스키마."""
from typing import Literal, Optional
from pydantic import BaseModel

from schemas.common import Place, ToolResult


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    lang: str = "en"  # ko | en | ja
    history: list[ChatMessage] = []


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
