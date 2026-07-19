"""DSPy 관광지·행사 후보 선정에 사용하는 입력·출력 계약."""

from datetime import date

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.config import settings


class AttractionConstraintEvidence(BaseModel):
    """구조화된 조건과 후보 문서의 일치 근거."""

    model_config = ConfigDict(extra="forbid")

    source_text: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    kind: str = Field(pattern="^(required|excluded)$")
    status: str = Field(pattern="^(match|conflict|unknown)$")
    evidence: list[str] = Field(default_factory=list)


class AttractionContextEvidence(BaseModel):
    """요청 시점 Context의 가용성과 출처를 손실 없이 전달한다."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["available", "unavailable"] = "unavailable"
    value: str | None = None
    basis: str | None = None
    observed_at: str | None = None

    @model_validator(mode="after")
    def reject_values_when_unavailable(self) -> "AttractionContextEvidence":
        if self.status == "unavailable" and any(
            value is not None
            for value in (self.value, self.basis, self.observed_at)
        ):
            raise ValueError("unavailable Context에는 값 또는 근거가 있을 수 없습니다.")
        return self


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
    congestion: AttractionContextEvidence = Field(default_factory=AttractionContextEvidence)
    weather: AttractionContextEvidence = Field(default_factory=AttractionContextEvidence)
    constraints: list[AttractionConstraintEvidence] = Field(default_factory=list)

    @field_validator("congestion", "weather", mode="before")
    @classmethod
    def normalize_missing_context(cls, value):
        """Accept legacy JSONL null as the explicit unavailable representation."""

        return {} if value is None else value


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
    "AttractionConstraintEvidence",
    "AttractionContextEvidence",
    "AttractionEvidenceCandidate",
    "AttractionSelection",
]
