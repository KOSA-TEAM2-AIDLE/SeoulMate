"""Deterministic safety checks for attraction DSPy predictions."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from domains.attraction.answer_models import AttractionAnswerInput
from domains.attraction.dspy.contracts import (
    AttractionAnswerContext,
    AttractionReasonPrediction,
    AttractionSelectionPrediction,
    AttractionStructuredAnswer,
)


class AttractionDspyValidationError(ValueError):
    """DSPy output violates the verified attraction evidence contract."""


def validate_selection_prediction(
    answer_input: AttractionAnswerInput,
    raw_prediction: Any,
) -> AttractionSelectionPrediction:
    try:
        prediction = AttractionSelectionPrediction.model_validate(raw_prediction)
    except ValidationError as error:
        raise AttractionDspyValidationError("잘못된 Selection DSPy 출력입니다.") from error

    candidates = {candidate.place_id: candidate for candidate in answer_input.candidates}
    selected_ids = set(prediction.selected_place_ids)
    forbidden_ids = set(prediction.forbidden_place_ids)
    if not selected_ids.issubset(candidates):
        raise AttractionDspyValidationError("선택 ID가 입력 후보에 없습니다.")
    if not forbidden_ids.issubset(candidates):
        raise AttractionDspyValidationError("제외 ID가 입력 후보에 없습니다.")
    if any(
        constraint.kind == "excluded" and constraint.status == "conflict"
        for place_id in selected_ids
        for constraint in candidates[place_id].constraints
    ):
        raise AttractionDspyValidationError("제외 조건과 충돌한 후보를 선택했습니다.")
    return prediction


def validate_reason_prediction(
    selected_place_ids: list[str],
    raw_prediction: Any,
) -> AttractionReasonPrediction:
    try:
        prediction = AttractionReasonPrediction.model_validate(raw_prediction)
    except ValidationError as error:
        raise AttractionDspyValidationError("잘못된 Reason DSPy 출력입니다.") from error
    if list(prediction.recommendation_reasons) != selected_place_ids:
        raise AttractionDspyValidationError("Reason ID가 Selection 결과와 일치하지 않습니다.")
    if any(not reason.strip() for reason in prediction.recommendation_reasons.values()):
        raise AttractionDspyValidationError("Reason 사유는 비어 있을 수 없습니다.")
    return prediction


def validate_structured_answer(
    answer_input: AttractionAnswerInput,
    selected_place_ids: list[str],
    raw_answer: Any,
) -> AttractionStructuredAnswer:
    try:
        answer = AttractionStructuredAnswer.model_validate(
            _normalize_structured_answer(raw_answer)
        )
    except ValidationError as error:
        raise AttractionDspyValidationError("잘못된 Answer DSPy 출력입니다.") from error

    candidates = {candidate.place_id: candidate for candidate in answer_input.candidates}
    selected = set(selected_place_ids)
    result_ids = [item.place_id for item in answer.recommendations]
    if len(result_ids) != len(set(result_ids)):
        raise AttractionDspyValidationError("추천 ID가 중복되었습니다.")
    if not set(result_ids).issubset(selected):
        raise AttractionDspyValidationError("Answer가 선택되지 않은 후보를 추천했습니다.")
    if result_ids != selected_place_ids:
        raise AttractionDspyValidationError(
            "Answer 추천 ID가 Selection 선택 결과와 일치하지 않습니다."
        )
    if any(item.name != candidates[item.place_id].name for item in answer.recommendations):
        raise AttractionDspyValidationError("Answer의 장소명이 입력 후보와 다릅니다.")
    if answer.language.casefold() != answer_input.language.casefold():
        raise AttractionDspyValidationError("Answer 언어가 요청 언어와 다릅니다.")
    for item in answer.recommendations:
        candidate = candidates[item.place_id]
        _validate_evidence(
            item.description_evidence,
            [candidate.description] if candidate.description else [],
            label="시설 근거",
        )
        _validate_evidence(item.review_evidence, candidate.reviews, label="리뷰 근거")
        _validate_context(item.congestion, candidate.congestion, label="혼잡도")
        _validate_context(item.weather, candidate.weather, label="날씨")
    return answer


def _validate_evidence(
    items: list[str],
    sources: list[str],
    *,
    label: str,
) -> None:
    normalized_sources = [_normalized_text(value) for value in sources if value]
    for item in items:
        normalized_item = _normalized_text(item)
        if not normalized_item or not any(
            normalized_item in source for source in normalized_sources
        ):
            raise AttractionDspyValidationError(f"{label}가 입력 후보에 없습니다.")


def _validate_context(
    actual: AttractionAnswerContext,
    expected: Any,
    *,
    label: str,
) -> None:
    if actual.model_dump() != expected.model_dump():
        raise AttractionDspyValidationError(
            f"{label} Context가 입력 후보와 다릅니다."
        )


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _normalize_structured_answer(raw_answer: Any) -> Any:
    """Normalize harmless JSON-shape variants before applying the strict contract."""

    if not isinstance(raw_answer, dict):
        return raw_answer
    normalized = dict(raw_answer)
    if normalized.get("no_result_reason") == "":
        normalized["no_result_reason"] = None
    recommendations = normalized.get("recommendations")
    if not isinstance(recommendations, list):
        return normalized
    normalized["recommendations"] = [dict(item) if isinstance(item, dict) else item for item in recommendations]
    for item in normalized["recommendations"]:
        if not isinstance(item, dict):
            continue
        for field in ("description_evidence", "review_evidence"):
            if isinstance(item.get(field), str):
                item[field] = [item[field]]
    return normalized


__all__ = [
    "AttractionDspyValidationError",
    "validate_reason_prediction",
    "validate_selection_prediction",
    "validate_structured_answer",
]
