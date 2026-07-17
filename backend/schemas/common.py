"""API 명세서 3-3, 3-4 참고: RAG 추천 장소 / MCP 도구 실행 결과 공통 스키마."""
from typing import Optional
from pydantic import BaseModel, Field


class Place(BaseModel):
    source_type: str  # cafe | restaurant | accommodation | event
    source_id: str
    # 식당 상세 API를 프론트에서 바로 호출할 수 있도록 범용 source_id와 별도로 노출한다.
    restaurant_id: Optional[str] = None
    task_id: Optional[str] = None
    name: str
    category: str
    score: float
    congestion: Optional[str] = None
    area_code: Optional[str] = None
    reason: str
    rank: Optional[int] = None
    selection_reason: Optional[str] = None
    # 프론트 최종 DTO는 GPT가 만든 텍스트가 아니라 검색/API에서 확인된
    # 상세 값만 복사한다. 도메인 검색기가 아직 제공하지 않는 값은 None이다.
    address: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    image: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    rag_score: Optional[float] = None
    weather_score: Optional[float] = None
    weather_reasons: list[str] = Field(default_factory=list)
    price: Optional[str] = None
    live_rating: Optional[str] = None
    link: Optional[str] = None
    features: Optional[str] = None


class ToolResult(BaseModel):
    tool_name: str
    params: dict
    result: dict
    ok: bool
    source: str  # live | mock
    error: Optional[str] = None
