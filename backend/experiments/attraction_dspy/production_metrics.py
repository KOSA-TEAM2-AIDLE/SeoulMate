"""Deterministic metrics for the split attraction DSPy programs.

The metrics deliberately score only fields that can be checked against the
offline example.  Natural-language quality remains a gold-test review concern;
an optimizer must never receive credit for an invalid or ungrounded structure.
"""

from __future__ import annotations

import json
from typing import Any

from domains.attraction.dspy.validator import (
    AttractionDspyValidationError,
    validate_selection_prediction,
    validate_reason_prediction,
    validate_structured_answer,
)
from experiments.attraction_dspy.production_dataset import ProductionDspyCase


def build_selection_metric(case_index: dict[str, ProductionDspyCase]):
    def metric(example, prediction, trace=None) -> float:
        case = _case_for(example, case_index)
        try:
            actual = validate_selection_prediction(
                case.answer_input,
                {
                    "selected_place_ids": list(prediction.selected_place_ids),
                    "forbidden_place_ids": list(prediction.forbidden_place_ids),
                    "selection_reasons": json.loads(prediction.selection_reasons_json),
                },
            )
        except (AttractionDspyValidationError, AttributeError, TypeError, json.JSONDecodeError):
            return 0.0
        return _id_score(actual.selected_place_ids, case.selected_place_ids)

    return metric


def build_answer_metric(case_index: dict[str, ProductionDspyCase]):
    def metric(example, prediction, trace=None) -> float:
        case = _case_for(example, case_index)
        try:
            raw_answer = json.loads(prediction.structured_answer_json)
            actual = validate_structured_answer(
                case.answer_input,
                case.selected_place_ids,
                raw_answer,
            )
        except (AttractionDspyValidationError, AttributeError, TypeError, json.JSONDecodeError):
            return 0.0
        expected_ids = (
            [item["place_id"] for item in case.structured_answer.get("recommendations", [])]
            if case.structured_answer
            else case.selected_place_ids
        )
        return _id_score(
            [item.place_id for item in actual.recommendations],
            expected_ids,
        )

    return metric


def build_reason_metric(case_index: dict[str, ProductionDspyCase]):
    def metric(example, prediction, trace=None) -> float:
        case = _case_for(example, case_index)
        try:
            validate_reason_prediction(
                case.selected_place_ids,
                {"recommendation_reasons": json.loads(prediction.recommendation_reasons_json)},
            )
        except (AttractionDspyValidationError, AttributeError, TypeError, json.JSONDecodeError):
            return 0.0
        return 1.0

    return metric


def _case_for(example: Any, case_index: dict[str, ProductionDspyCase]) -> ProductionDspyCase:
    case_id = str(getattr(example, "case_id", ""))
    try:
        return case_index[case_id]
    except KeyError as error:
        raise ValueError(f"등록되지 않은 production case_id입니다: {case_id}") from error


def _id_score(actual: list[str], expected: list[str]) -> float:
    if actual == expected:
        return 1.0
    actual_set, expected_set = set(actual), set(expected)
    if not actual_set and not expected_set:
        return 1.0
    return len(actual_set & expected_set) / len(actual_set | expected_set)


__all__ = ["build_answer_metric", "build_reason_metric", "build_selection_metric"]
