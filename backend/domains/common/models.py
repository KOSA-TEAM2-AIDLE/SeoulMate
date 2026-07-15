"""모든 장소 검색기가 공유하는 내부 입력·출력 계약."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DomainSearchRequest(BaseModel):
    """첫 GPT의 Structured Query를 도메인 검색기에 전달하는 정규화 입력."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    task_id: str
    domain: str
    language: str = "ko"
    search_query: str
    themes: list[str] = Field(default_factory=list)
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    current_location_name: str | None = None
    radius_km: float | None = None
    visit_date: date | None = None
    start_time: str | None = None
    end_time: str | None = None
    party_size: int | None = None
    budget_min_krw: int | None = None
    budget_max_krw: int | None = None
    required_features: list[str] = Field(default_factory=list)
    excluded_features: list[str] = Field(default_factory=list)
    candidate_count: int = Field(default=10, ge=1, le=100)
    # 기존 식당 RAG가 StructuredTravelQuery 전체를 아직 필요로 하는 동안만 사용하는
    # 단계적 마이그레이션용 문맥이다. 외부 API 응답에는 직렬화하지 않는다.
    context: dict[str, Any] = Field(default_factory=dict, exclude=True)


class SearchCandidate(BaseModel):
    """도메인 검색 및 공통 컨텍스트 재랭킹의 표준 후보."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    place_id: str
    task_id: str
    name: str
    category: str
    latitude: float | None = None
    longitude: float | None = None
    base_score: float
    final_score: float
    evidence: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    signals: dict[str, Any] = Field(default_factory=dict)

    @property
    def candidate_id(self) -> str:
        return f"{self.domain}:{self.place_id}"


__all__ = ["DomainSearchRequest", "SearchCandidate"]

