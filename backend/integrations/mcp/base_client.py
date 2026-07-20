"""MCP가 반환하는 공통 컨텍스트 계약."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class ContextRequest(BaseModel):
    query: str
    latitude: float
    longitude: float
    language: str = "ko"
    place_name: str | None = None
    target_date: str | None = None
    target_time: str | None = None


class ContextResult(BaseModel):
    provider: str
    available: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ContextProvider(Protocol):
    name: str
    implemented: bool

    async def get_context(self, request: ContextRequest) -> ContextResult: ...


__all__ = ["ContextRequest", "ContextResult", "ContextProvider"]

