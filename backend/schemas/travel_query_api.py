from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

from schemas.hitl import HumanInTheLoopResponse


class TravelQueryStartRequest(BaseModel):
    message: str = Field(min_length=1)
    language: Literal["ko", "en"] = "ko"
    reference_at: datetime | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    location_name: str | None = None

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


class TravelQueryApiResponse(HumanInTheLoopResponse):
    thread_id: str = Field(min_length=1)
