"""API 명세서 3-3, 3-4 참고: RAG 추천 장소 / MCP 도구 실행 결과 공통 스키마."""
from typing import Optional
from pydantic import BaseModel


class Place(BaseModel):
    source_type: str  # cafe | restaurant | accommodation | event
    source_id: str
    name: str
    category: str
    score: float
    congestion: Optional[str] = None
    area_code: Optional[str] = None
    reason: str


class ToolResult(BaseModel):
    tool_name: str
    params: dict
    result: dict
    ok: bool
    source: str  # live | mock
    error: Optional[str] = None
