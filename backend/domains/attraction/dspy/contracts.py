"""Selection/Answer DSPy programs shared output contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AttractionSelectionPrediction(BaseModel):
    """Validated IDs and reasons emitted by the selection program."""

    model_config = ConfigDict(extra="forbid")

    selected_place_ids: list[str] = Field(default_factory=list, max_length=3)
    forbidden_place_ids: list[str] = Field(default_factory=list)
    selection_reasons: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ids_and_reasons(self) -> "AttractionSelectionPrediction":
        if len(self.selected_place_ids) != len(set(self.selected_place_ids)):
            raise ValueError("selected_place_ids는 중복될 수 없습니다.")
        if set(self.selected_place_ids) & set(self.forbidden_place_ids):
            raise ValueError("선택 후보와 제외 후보는 겹칠 수 없습니다.")
        if set(self.selection_reasons) != set(self.selected_place_ids):
            raise ValueError("selection_reasons의 ID는 선택 후보와 일치해야 합니다.")
        if any(not reason.strip() for reason in self.selection_reasons.values()):
            raise ValueError("selection_reason은 비어 있을 수 없습니다.")
        return self


class AttractionAnswerContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available", "unavailable"]
    value: str | None = None
    basis: str | None = None
    observed_at: str | None = None

    @model_validator(mode="after")
    def validate_availability(self) -> "AttractionAnswerContext":
        if self.status == "unavailable" and any(
            value is not None
            for value in (self.value, self.basis, self.observed_at)
        ):
            raise ValueError("unavailable Context에는 값이 있을 수 없습니다.")
        if self.status == "available" and self.value is None:
            raise ValueError("available Context에는 value가 필요합니다.")
        return self


class AttractionStructuredRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    place_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    recommendation_reason: str = Field(min_length=1)
    description_evidence: list[str] = Field(default_factory=list)
    review_evidence: list[str] = Field(default_factory=list)
    congestion: AttractionAnswerContext
    weather: AttractionAnswerContext
    visitor_note: str | None = None


class AttractionStructuredAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(min_length=1)
    recommendations: list[AttractionStructuredRecommendation] = Field(
        default_factory=list,
        max_length=3,
    )
    no_result_reason: str | None = None

    @model_validator(mode="after")
    def validate_empty_result_reason(self) -> "AttractionStructuredAnswer":
        if not self.recommendations and not (
            self.no_result_reason and self.no_result_reason.strip()
        ):
            raise ValueError("추천이 없으면 no_result_reason이 필요합니다.")
        if self.recommendations and self.no_result_reason is not None:
            raise ValueError("추천이 있으면 no_result_reason은 null이어야 합니다.")
        return self


__all__ = [
    "AttractionAnswerContext",
    "AttractionSelectionPrediction",
    "AttractionStructuredAnswer",
    "AttractionStructuredRecommendation",
]

