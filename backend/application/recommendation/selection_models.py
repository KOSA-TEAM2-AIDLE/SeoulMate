"""도메인별 후보 선택기가 공통 Chat 계층에 반환하는 계약."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CandidateSelection(BaseModel):
    """검증된 원본 후보 ID와 사용자에게 보여줄 선정 이유."""

    model_config = ConfigDict(extra="forbid")

    place_id: str = Field(min_length=1)
    selection_reason: str = Field(min_length=1)


class CandidateSelectionResult(BaseModel):
    """도메인 선택 전략이 반환하는 답변과 순서가 보존된 선택 목록."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    selections: list[CandidateSelection] = Field(
        default_factory=list,
        max_length=10,
    )
    used_fallback: bool = False

    @model_validator(mode="after")
    def reject_duplicate_place_ids(self) -> "CandidateSelectionResult":
        place_ids = [selection.place_id for selection in self.selections]
        if len(place_ids) != len(set(place_ids)):
            raise ValueError("선택된 place_id는 중복될 수 없습니다.")
        return self


__all__ = ["CandidateSelection", "CandidateSelectionResult"]
