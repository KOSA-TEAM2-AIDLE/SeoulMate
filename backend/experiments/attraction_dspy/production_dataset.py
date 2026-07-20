"""Adapter from generated DSPy JSONL into the live attraction evidence contract."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import dspy

from domains.attraction.answer_models import (
    AttractionAnswerInput,
    AttractionContextEvidence,
    AttractionEvidenceCandidate,
)


@dataclass(frozen=True)
class ProductionDspyCase:
    case_id: str
    answer_input: AttractionAnswerInput
    selected_place_ids: list[str]
    forbidden_place_ids: list[str]
    selection_reasons: dict[str, str]
    structured_answer: dict[str, Any] | None


def adapt_production_example(raw: dict[str, Any]) -> ProductionDspyCase:
    payload = raw["input"]
    candidates = [
        AttractionEvidenceCandidate(
            place_id=item["place_id"],
            rank=item["rank"],
            name=item["name"],
            category=item["category"],
            distance_m=item.get("distance_m"),
            description=item.get("description"),
            reviews=item.get("reviews") or [],
            congestion=_context(item.get("congestion")),
            weather=_context(item.get("weather")),
            constraints=item.get("constraints") or [],
        )
        for item in payload.get("candidates") or []
    ]
    answer_input = AttractionAnswerInput(
        question=payload["question"],
        language=payload["language"],
        location=payload.get("location"),
        themes=payload.get("themes") or [],
        candidates=candidates,
    )
    expected = raw.get("expected") or {}
    return ProductionDspyCase(
        case_id=raw["example_id"],
        answer_input=answer_input,
        selected_place_ids=list(expected.get("selected_place_ids") or []),
        forbidden_place_ids=list(expected.get("forbidden_place_ids") or []),
        selection_reasons=dict(expected.get("selection_reasons") or {}),
        structured_answer=(
            dict(expected["structured_answer"])
            if isinstance(expected.get("structured_answer"), dict)
            else None
        ),
    )


def load_production_splits(
    dataset_root: str | Path,
    dataset_kind: str,
) -> dict[str, list[ProductionDspyCase]]:
    """Load generated JSONL without mixing train/dev/test or gold evaluation."""

    root = Path(dataset_root)
    if dataset_kind == "gold_test":
        paths = {"test": root / "gold_test" / "gold_test.jsonl"}
    else:
        paths = {
            split: root / dataset_kind / f"{split}.jsonl"
            for split in ("train", "dev", "test")
        }
    result: dict[str, list[ProductionDspyCase]] = {}
    seen: set[str] = set()
    for split, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"DSPy dataset split이 없습니다: {path}")
        cases = [
            adapt_production_example(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        duplicate = seen.intersection(case.case_id for case in cases)
        if duplicate:
            raise ValueError(f"DSPy split 간 example_id 중복: {sorted(duplicate)}")
        seen.update(case.case_id for case in cases)
        result[split] = cases
    return result


def _context(value: Any) -> AttractionContextEvidence:
    if value is None:
        return AttractionContextEvidence()
    if isinstance(value, dict):
        return AttractionContextEvidence.model_validate(value)
    return AttractionContextEvidence(status="available", value=str(value))


def to_selection_example(case: ProductionDspyCase) -> dspy.Example:
    payload = case.answer_input
    return dspy.Example(
        case_id=case.case_id,
        language=payload.language,
        question=payload.question,
        location=payload.location or "",
        themes_json=json.dumps(payload.themes, ensure_ascii=False),
        selection_count=min(3, len(payload.candidates)),
        candidates_json=json.dumps(
            [candidate.model_dump(mode="json") for candidate in payload.candidates],
            ensure_ascii=False,
        ),
    ).with_inputs(
        "language", "question", "location", "themes_json", "selection_count", "candidates_json"
    )


def to_answer_example(case: ProductionDspyCase) -> dspy.Example:
    selected = [
        candidate
        for candidate in case.answer_input.candidates
        if candidate.place_id in set(case.selected_place_ids)
    ]
    return dspy.Example(
        case_id=case.case_id,
        language=case.answer_input.language,
        question=case.answer_input.question,
        selected_candidates_json=json.dumps(
            [candidate.model_dump(mode="json") for candidate in selected],
            ensure_ascii=False,
        ),
        selection_reasons_json=json.dumps(case.selection_reasons, ensure_ascii=False),
    ).with_inputs(
        "language", "question", "selected_candidates_json", "selection_reasons_json"
    )


def to_reason_example(case: ProductionDspyCase) -> dspy.Example:
    selected = [
        {
            "place_id": candidate.place_id,
            "name": candidate.name,
            "category": candidate.category,
        }
        for candidate in case.answer_input.candidates
        if candidate.place_id in set(case.selected_place_ids)
    ]
    return dspy.Example(
        case_id=case.case_id,
        language=case.answer_input.language,
        question=case.answer_input.question,
        selected_candidates_json=json.dumps(selected, ensure_ascii=False),
        selection_reasons_json=json.dumps(case.selection_reasons, ensure_ascii=False),
    ).with_inputs(
        "language", "question", "selected_candidates_json", "selection_reasons_json"
    )


__all__ = [
    "ProductionDspyCase",
    "adapt_production_example",
    "load_production_splits",
    "to_answer_example",
    "to_reason_example",
    "to_selection_example",
]
