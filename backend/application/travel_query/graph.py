import json
from datetime import datetime
from typing import Any, Literal

from langchain_core.runnables import Runnable
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from application.travel_query.checkpoint import (
    create_development_checkpointer,
)
from application.travel_query.extraction import (
    IntentExtraction,
    TravelIntentExtractor,
)
from application.travel_query.required_info import (
    check_required_information,
)
from application.travel_query.state import TravelQueryGraphState
from schemas.hitl import HumanInTheLoopResponse


def ask_user(state: TravelQueryGraphState) -> Command[Literal["merge_answer"]]:
    """필수 정보 질문을 외부로 전달하고 같은 노드에서 재개한다."""
    payload = HumanInTheLoopResponse(
        status="collecting",
        assistant_message=state["assistant_message"],
        missing_fields=state["missing_fields"],
        collected=state.get("collected", {}),
    ).model_dump(mode="json")
    answer = interrupt(payload)
    return Command(
        update={"latest_user_answer": answer},
        goto="merge_answer",
    )


def merge_user_answer(
    state: TravelQueryGraphState,
) -> TravelQueryGraphState:
    """재개된 사용자 답변을 기록하고 재추출할 수 있게 보존한다."""
    answer = state.get("latest_user_answer")
    if isinstance(answer, str):
        answer_text = answer
    else:
        answer_text = json.dumps(answer, ensure_ascii=False, default=str)

    history = list(state.get("conversation_history", []))
    history.extend(
        [
            {
                "role": "assistant",
                "content": state.get("assistant_message") or "",
            },
            {"role": "user", "content": answer_text},
        ]
    )
    return {"conversation_history": history}


def _route_after_required_check(
    state: TravelQueryGraphState,
) -> Literal["ask_user", "finish"]:
    if state.get("status") == "collecting":
        return "ask_user"
    return "finish"


def build_travel_query_graph(
    extraction_chain: Runnable[
        dict[str, Any],
        IntentExtraction | dict[str, Any],
    ],
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    builder = StateGraph(TravelQueryGraphState)
    builder.add_node("extract", TravelIntentExtractor(extraction_chain))
    builder.add_node("check_required", check_required_information)
    builder.add_node("ask_user", ask_user)
    builder.add_node("merge_answer", merge_user_answer)

    builder.add_edge(START, "extract")
    builder.add_edge("extract", "check_required")
    builder.add_conditional_edges(
        "check_required",
        _route_after_required_check,
        {
            "ask_user": "ask_user",
            "finish": END,
        },
    )
    builder.add_edge("merge_answer", "extract")

    return builder.compile(
        checkpointer=checkpointer or create_development_checkpointer(),
        name="seoulmate_travel_query_hitl",
    )


def build_initial_state(
    original_question: str,
    reference_at: datetime,
    *,
    language: Literal["ko", "en"] = "ko",
    current_latitude: float | None = None,
    current_longitude: float | None = None,
    current_location_name: str | None = None,
) -> TravelQueryGraphState:
    if not original_question.strip():
        raise ValueError("original_question은 비어 있을 수 없습니다.")
    if reference_at.tzinfo is None or reference_at.utcoffset() is None:
        raise ValueError("reference_at은 시간대 정보가 있는 날짜여야 합니다.")
    if (current_latitude is None) != (current_longitude is None):
        raise ValueError("현재 위치의 위도와 경도는 함께 제공해야 합니다.")
    if current_latitude is not None and not -90 <= current_latitude <= 90:
        raise ValueError("current_latitude 범위가 올바르지 않습니다.")
    if current_longitude is not None and not -180 <= current_longitude <= 180:
        raise ValueError("current_longitude 범위가 올바르지 않습니다.")

    return {
        "status": "collecting",
        "original_question": original_question,
        "language": language,
        "reference_at": reference_at,
        "current_latitude": current_latitude,
        "current_longitude": current_longitude,
        "current_location_name": current_location_name,
        "collected": {
            "original_question": original_question,
            "language": language,
        },
        "missing_fields": [],
        "assistant_message": None,
        "latest_user_answer": None,
        "structured_query": None,
        "validation_errors": [],
        "repair_attempts": 0,
        "conversation_history": [],
    }
