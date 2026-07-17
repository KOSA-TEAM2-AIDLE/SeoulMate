"""DSPy 관광지·행사 후보 선정에 사용하는 입력·출력 계약."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.config import settings


class AttractionEvidenceCandidate(BaseModel):
    """DSPy에 노출해도 되는 검증된 후보 근거."""

    model_config = ConfigDict(extra="forbid")

    place_id: str = Field(min_length=1)
    rank: int = Field(ge=1)
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    distance_m: float | None = Field(default=None, ge=0)
    description: str | None = None
    reviews: list[str] = Field(default_factory=list, max_length=5)
    event_start_date: date | None = None
    event_end_date: date | None = None
    congestion: str | None = None


class AttractionAnswerInput(BaseModel):
    """재랭킹이 완료된 최대 10개 후보를 담는 DSPy 입력."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    language: str = Field(min_length=1)
    location: str | None = None
    themes: list[str] = Field(default_factory=list)
    candidates: list[AttractionEvidenceCandidate] = Field(
        default_factory=list,
        max_length=10,
    )

    @model_validator(mode="after")
    def reject_duplicate_candidate_ids(self) -> "AttractionAnswerInput":
        place_ids = [candidate.place_id for candidate in self.candidates]
        if len(place_ids) != len(set(place_ids)):
            raise ValueError("후보 place_id는 중복될 수 없습니다.")
        return self


class AttractionSelection(BaseModel):
    """DSPy가 선정한 후보와 후보 근거."""

    model_config = ConfigDict(extra="forbid")

    place_id: str = Field(min_length=1)
    selection_reason: str = Field(min_length=1)


class AttractionAnswerResult(BaseModel):
    """관광 도메인이 채팅 계층에 전달할 최종 결과."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    selections: list[AttractionSelection] = Field(
        default_factory=list,
        max_length=10,
    )
    used_fallback: bool = False

    @model_validator(mode="after")
    def reject_duplicate_selection_ids(self) -> "AttractionAnswerResult":
        place_ids = [selection.place_id for selection in self.selections]
        if len(place_ids) > settings.attraction_recommendation_limit:
            raise ValueError(
                "선정 후보는 설정된 최대 추천 개수를 넘을 수 없습니다."
            )
        if len(place_ids) != len(set(place_ids)):
            raise ValueError("선정된 place_id는 중복될 수 없습니다.")
        return self


__all__ = [
    "AttractionAnswerInput",
    "AttractionAnswerResult",
    "AttractionEvidenceCandidate",
    "AttractionSelection",
]
