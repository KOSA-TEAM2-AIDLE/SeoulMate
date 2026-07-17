from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

from domains.common.models import SearchCandidate
from schemas.hitl import HumanInTheLoopResponse
from schemas.structured_query import StructuredTravelQuery, TaskDomain


class TravelQueryContextMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class TravelQueryStartRequest(BaseModel):
    message: str = Field(min_length=1)
    language: Literal["ko", "en"] = "ko"
    reference_at: datetime | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    location_name: str | None = None
    history: list[TravelQueryContextMessage] = Field(
        default_factory=list,
        max_length=12,
    )
    previous_structured_query: StructuredTravelQuery | None = None

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        if not self.message.strip():
            raise ValueError("message는 공백일 수 없습니다.")
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat과 lng는 함께 제공해야 합니다.")
        if (
            self.reference_at is not None
            and (
                self.reference_at.tzinfo is None
                or self.reference_at.utcoffset() is None
            )
        ):
            raise ValueError("reference_at에는 시간대 정보가 필요합니다.")
        return self


class TravelQueryResumeRequest(BaseModel):
    answer: str | dict[str, Any]

    @model_validator(mode="after")
    def validate_answer(self) -> Self:
        if isinstance(self.answer, str) and not self.answer.strip():
            raise ValueError("answer는 공백일 수 없습니다.")
        if isinstance(self.answer, dict) and not self.answer:
            raise ValueError("answer 객체는 비어 있을 수 없습니다.")
        return self


class DomainAgentDispatchResult(BaseModel):
    domain: TaskDomain
    status: Literal["completed", "placeholder"] = "placeholder"
    task_ids: list[str] = Field(default_factory=list)
    candidates: list[SearchCandidate] = Field(default_factory=list)
    assistant_message: str


class TravelQueryExecutionContext(BaseModel):
    """도메인 실행에만 쓰고 API JSON에는 노출하지 않는 요청 문맥."""

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_name: str | None = None

    @model_validator(mode="after")
    def validate_coordinates(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("실행 컨텍스트의 위도와 경도는 함께 필요합니다.")
        return self


class TravelQueryApiResponse(HumanInTheLoopResponse):
    thread_id: str = Field(min_length=1)
    current_latitude: float | None = Field(default=None, ge=-90, le=90)
    current_longitude: float | None = Field(default=None, ge=-180, le=180)
    current_location_name: str | None = None
    agent_dispatches: list[DomainAgentDispatchResult] = Field(
        default_factory=list
    )
