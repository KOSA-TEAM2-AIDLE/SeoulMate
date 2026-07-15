from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from application.travel_query.extraction import create_intent_extraction_chain
from application.travel_query.graph import (
    build_initial_state,
    build_travel_query_graph,
)
from core.config import settings
from schemas.travel_query_api import (
    TravelQueryApiResponse,
    TravelQueryStartRequest,
)


SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")


class TravelQueryConfigurationError(RuntimeError):
    pass


class TravelQueryThreadNotFoundError(LookupError):
    pass


class TravelQueryThreadCompletedError(RuntimeError):
    pass


class TravelQueryExecutionError(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("StructuredTravelQuery 생성에 실패했습니다.")


class TravelQueryService:
    def __init__(self, graph: CompiledStateGraph) -> None:
        self._graph = graph

    async def start(
        self,
        request: TravelQueryStartRequest,
    ) -> TravelQueryApiResponse:
        thread_id = str(uuid4())
        config = _thread_config(thread_id)
        initial_state = build_initial_state(
            request.message,
            request.reference_at or datetime.now(SEOUL_TIMEZONE),
            language=request.language,
            current_latitude=request.lat,
            current_longitude=request.lng,
            current_location_name=request.location_name,
        )
        result = await self._graph.ainvoke(initial_state, config=config)
        return _to_api_response(thread_id, result)

    async def resume(
        self,
        thread_id: str,
        answer: str | dict[str, Any],
    ) -> TravelQueryApiResponse:
        config = _thread_config(thread_id)
        snapshot = await self._graph.aget_state(config)
        if not snapshot.values:
            raise TravelQueryThreadNotFoundError(thread_id)
        if not snapshot.next:
            raise TravelQueryThreadCompletedError(thread_id)

        result = await self._graph.ainvoke(Command(resume=answer), config=config)
        return _to_api_response(thread_id, result)


@lru_cache
def get_travel_query_service() -> TravelQueryService:
    if settings.openai_api_key is None:
        raise TravelQueryConfigurationError(
            "OPENAI_API_KEY가 설정되지 않았습니다."
        )
    model = ChatOpenAI(
        model=settings.openai_chat_model,
        api_key=settings.openai_api_key.get_secret_value(),
        temperature=0,
        max_retries=2,
    )
    graph = build_travel_query_graph(create_intent_extraction_chain(model))
    return TravelQueryService(graph)


def _thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def _to_api_response(
    thread_id: str,
    result: dict[str, Any],
) -> TravelQueryApiResponse:
    interrupts = result.get("__interrupt__") or []
    if interrupts:
        return TravelQueryApiResponse.model_validate(
            {"thread_id": thread_id, **interrupts[0].value}
        )

    status = result.get("status")
    if status == "ready":
        return TravelQueryApiResponse(
            thread_id=thread_id,
            status="ready",
            structured_query=result.get("structured_query"),
        )
    if status == "unsupported":
        return TravelQueryApiResponse(
            thread_id=thread_id,
            status="unsupported",
            assistant_message=result.get("assistant_message"),
        )
    raise TravelQueryExecutionError(result.get("validation_errors", []))
