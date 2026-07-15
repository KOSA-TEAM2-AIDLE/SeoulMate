from typing import Any, Literal, Self
from pydantic import BaseModel, Field, model_validator
from schemas.structured_query import StructuredTravelQuery, TravelIntent

class HumanInTheLoopResponse(BaseModel):
    status: Literal["collecting", "unsupported", "ready"]
    assistant_message: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    collected: dict[str, Any] = Field(default_factory=dict)
    structured_query: StructuredTravelQuery | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status == "collecting":
            if not self.assistant_message or not self.missing_fields:
                raise ValueError(
                    "collecting 상태에는 질문과 missing_fields가 필요합니다."
                )
            if self.structured_query is not None:
                raise ValueError(
                    "collecting 상태에는 structured_query를 전달할 수 없습니다."
                )
        elif self.status == "unsupported":
            if self.assistant_message != "루트 수정은 지원하지 않습니다.":
                raise ValueError(
                    "unsupported 상태에는 지원하지 않음 안내가 필요합니다."
                )
            if self.missing_fields or self.structured_query is not None:
                raise ValueError(
                    "unsupported 상태에는 질문이나 structured_query를 포함할 수 없습니다."
                )
        elif (
            self.assistant_message is not None
            or self.missing_fields
            or self.collected
            or self.structured_query is None
        ):
            raise ValueError(
                "ready 상태에는 확정된 structured_query만 포함해야 합니다."
            )
        return self


class CollectedTravelInfo(BaseModel):
    original_question: str = Field(min_length=1)
    language: Literal["ko", "en"] = "ko"
    intent: TravelIntent | None = None
    values: dict[str, Any] = Field(default_factory=dict)
