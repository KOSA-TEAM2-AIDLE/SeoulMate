from typing import Any, Literal, TypedDict

from schemas.structured_query import StructuredTravelQuery, TravelIntent


class TravelQueryGraphState(TypedDict, total=False):
    """LangGraph 노드 간에 공유하는 첫 GPT의 내부 상태."""

    status: Literal["collecting", "ready", "failed"]
    original_question: str
    language: Literal["ko", "en"]
    intent: TravelIntent
    collected: dict[str, Any]
    missing_fields: list[str]
    assistant_message: str | None
    latest_user_answer: str | dict[str, Any] | None
    structured_query: StructuredTravelQuery | None
    validation_errors: list[str]
    repair_attempts: int
