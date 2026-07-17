"""관광 DSPy 오프라인 데이터셋 계약과 누수 방지 loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import dspy
from pydantic import BaseModel, ConfigDict, Field, model_validator

from domains.attraction.answer_models import AttractionEvidenceCandidate


SPLIT_NAMES = ("train", "dev", "test", "blind")
DEFAULT_SPLIT_COUNTS = {"train": 30, "dev": 10, "test": 10, "blind": 20}


class DatasetIntegrityError(ValueError):
    """데이터셋 split·라벨·누수 계약을 위반했을 때 발생한다."""


class AttractionCaseSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    source_case_id: str = Field(min_length=1)


class AttractionDspyPublicInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    language: str = Field(min_length=1)
    location: str | None = None
    themes: list[str] = Field(default_factory=list)
    selection_count: int = Field(default=3, ge=1, le=3)
    candidates: list[AttractionEvidenceCandidate] = Field(
        min_length=5,
        max_length=10,
    )

    @model_validator(mode="after")
    def validate_candidate_contract(self) -> "AttractionDspyPublicInput":
        place_ids = [candidate.place_id for candidate in self.candidates]
        if len(place_ids) != len(set(place_ids)):
            raise ValueError("공개 후보 ID는 중복될 수 없습니다.")
        if self.selection_count > len(self.candidates):
            raise ValueError("선택 개수가 후보 수보다 많습니다.")
        return self


class AttractionDspyPrivateLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acceptable_place_ids: list[str] = Field(min_length=1)
    required_conditions: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    reference_answer: str | None = None
    human_review_status: Literal["reviewed", "provisional", "needs_review"]


class AttractionDspyCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    source: AttractionCaseSource
    public_input: AttractionDspyPublicInput
    private_label: AttractionDspyPrivateLabel

    @model_validator(mode="after")
    def validate_private_ids_exist_in_public_candidates(self) -> "AttractionDspyCase":
        public_ids = {
            candidate.place_id for candidate in self.public_input.candidates
        }
        if not set(self.private_label.acceptable_place_ids).issubset(public_ids):
            raise ValueError("허용 ID가 공개 후보에 존재하지 않습니다.")
        return self


def load_dataset_splits(
    data_dir: str | Path,
    *,
    expected_counts: dict[str, int] | None = None,
    allow_provisional: bool = False,
) -> dict[str, list[AttractionDspyCase]]:
    """JSONL split을 검증하고 훈련에 안전한 검수 완료 케이스만 로드한다."""

    directory = Path(data_dir)
    counts = expected_counts or DEFAULT_SPLIT_COUNTS
    if set(counts) != set(SPLIT_NAMES):
        raise DatasetIntegrityError("예상 split은 train/dev/test/blind 전체를 포함해야 합니다.")

    splits: dict[str, list[AttractionDspyCase]] = {}
    case_owner: dict[str, str] = {}
    for split in SPLIT_NAMES:
        path = directory / f"{split}.jsonl"
        if not path.is_file():
            raise DatasetIntegrityError(f"데이터셋 split이 없습니다: {path}")
        cases = _read_cases(path)
        if len(cases) != counts[split]:
            raise DatasetIntegrityError(
                f"{split} split 개수가 {counts[split]}이 아닙니다: {len(cases)}"
            )
        for case in cases:
            allowed_statuses = {"reviewed", "provisional"} if allow_provisional else {"reviewed"}
            if case.private_label.human_review_status not in allowed_statuses:
                raise DatasetIntegrityError(
                    f"사람 검수가 안 된 라벨입니다: {case.case_id}"
                )
            previous = case_owner.get(case.case_id)
            if previous is not None:
                raise DatasetIntegrityError(
                    f"case_id가 {previous}/{split} split에 중복됩니다: {case.case_id}"
                )
            case_owner[case.case_id] = split
        splits[split] = cases
    return splits


def to_dspy_example(case: AttractionDspyCase) -> dspy.Example:
    """private label을 완전히 제외한 optimizer 입력을 만든다."""

    public = case.public_input
    return dspy.Example(
        case_id=case.case_id,
        language=public.language,
        question=public.question,
        location=public.location or "",
        themes_json=json.dumps(public.themes, ensure_ascii=False),
        selection_count=public.selection_count,
        candidates_json=json.dumps(
            [candidate.model_dump(mode="json") for candidate in public.candidates],
            ensure_ascii=False,
        ),
    ).with_inputs(
        "language",
        "question",
        "location",
        "themes_json",
        "selection_count",
        "candidates_json",
    )


def _read_cases(path: Path) -> list[AttractionDspyCase]:
    cases = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(AttractionDspyCase.model_validate_json(line))
        except Exception as error:
            raise DatasetIntegrityError(
                f"잘못된 JSONL 케이스입니다: {path}:{line_number}"
            ) from error
    return cases


__all__ = [
    "AttractionDspyCase",
    "AttractionDspyPrivateLabel",
    "AttractionDspyPublicInput",
    "DatasetIntegrityError",
    "load_dataset_splits",
    "to_dspy_example",
]
