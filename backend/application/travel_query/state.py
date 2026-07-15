from datetime import datetime
from typing import Any, Literal, TypedDict

from schemas.structured_query import TravelIntent


class TravelQueryGraphState(TypedDict, total=False):
    """LangGraph 노드 간에 공유하는 첫 GPT의 내부 상태."""

    status: Literal[
        "collecting",
        "building",
        "repairing",
        "unsupported",
        "ready",
        "failed",
    ]
    original_question: str
    normalized_question: str
    language: Literal["ko", "en"]
    intent: TravelIntent
    reference_at: datetime
    current_latitude: float | None
    current_longitude: float | None
    current_location_name: str | None
    collected: dict[str, Any]
    missing_fields: list[str]
    assistant_message: str | None
    latest_user_answer: str | dict[str, Any] | None
    conversation_history: list[dict[str, str]]
    structured_query: dict[str, Any] | None
    validation_errors: list[str]
    repair_attempts: int
