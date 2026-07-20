"""DSPy 예측을 검증하고 안전한 정적 fallback을 제공한다."""

from __future__ import annotations

import json
from typing import Any

from core.config import settings
from domains.attraction.answer_diagnostics import (
    AttractionFallbackReason,
    AttractionPredictionValidationError,
)
from domains.attraction.answer_models import (
    AttractionAnswerInput,
    AttractionAnswerResult,
    AttractionSelection,
)
from domains.attraction.value_normalization import is_nullish


_QUIETNESS_TERMS = (
    "한적",
    "붐비지",
    "덜 붐",
    "혼잡하지",
    "uncrowded",
    "not crowded",
    "less crowded",
    "not busy",
)


def validate_attraction_prediction(
    answer_input: AttractionAnswerInput,
    prediction: Any,
) -> AttractionAnswerResult:
    """예측이 계약을 하나라도 위반하면 전체 fallback으로 전환한다."""

    try:
        return validate_attraction_prediction_or_raise(answer_input, prediction)
    except AttractionPredictionValidationError:
        return fallback_attraction_answer(answer_input)


def validate_attraction_prediction_or_raise(
    answer_input: AttractionAnswerInput,
    prediction: Any,
) -> AttractionAnswerResult:
    """검증 실패 원인을 상위 생성기가 로깅할 수 있게 전달한다."""

    candidates_by_id = {
        candidate.place_id: candidate for candidate in answer_input.candidates
    }
    candidate_ids_by_name = _unique_candidate_ids_by_name(answer_input)

    try:
        selected_references = prediction.selected_place_ids
    except AttributeError as error:
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.INVALID_SELECTED_IDS
        ) from error
    if not isinstance(selected_references, list) or not all(
        isinstance(reference, str) and not is_nullish(reference)
        for reference in selected_references
    ):
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.INVALID_SELECTED_IDS
        )
    selected_ids = [
        _resolve_candidate_id(reference, candidates_by_id, candidate_ids_by_name)
        for reference in selected_references
    ]
    if any(place_id is None for place_id in selected_ids):
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.UNKNOWN_SELECTED_ID
        )
    selected_ids = [place_id for place_id in selected_ids if place_id is not None]

    expected_count = min(
        settings.attraction_recommendation_limit,
        len(answer_input.candidates),
    )
    if len(selected_ids) > expected_count:
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.TOO_MANY_SELECTED_IDS
        )
    if len(selected_ids) != len(set(selected_ids)):
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.DUPLICATE_SELECTED_IDS
        )

    try:
        raw_reasons = json.loads(prediction.selection_reasons_json)
    except (AttributeError, TypeError, json.JSONDecodeError) as error:
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.INVALID_REASONS_JSON
        ) from error
    if not isinstance(raw_reasons, dict):
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.REASONS_ID_MISMATCH
        )
    reasons: dict[str, Any] = {}
    for reference, reason in raw_reasons.items():
        if not isinstance(reference, str):
            raise AttractionPredictionValidationError(
                AttractionFallbackReason.REASONS_ID_MISMATCH
            )
        place_id = _resolve_candidate_id(
            reference, candidates_by_id, candidate_ids_by_name
        )
        if place_id is None or place_id in reasons:
            raise AttractionPredictionValidationError(
                AttractionFallbackReason.REASONS_ID_MISMATCH
            )
        reasons[place_id] = reason
    if set(reasons) != set(selected_ids):
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.REASONS_ID_MISMATCH
        )
    if any(
        not isinstance(reasons[place_id], str)
        or is_nullish(reasons[place_id])
        for place_id in selected_ids
    ):
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.EMPTY_SELECTION_REASON
        )

    try:
        answer = prediction.answer
    except AttributeError as error:
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.EMPTY_ANSWER
        ) from error
    if not isinstance(answer, str) or is_nullish(answer):
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.EMPTY_ANSWER
        )
    normalized_answer = answer.casefold()
    mentioned_ids = {
        candidate.place_id
        for candidate in answer_input.candidates
        if candidate.name.casefold() in normalized_answer
    }
    # 자연어 답변에서 선택 장소 일부를 생략하는 것은 허용하되,
    # 선택하지 않은 후보를 추천하는 경우만 fallback 처리한다.
    if mentioned_ids - set(selected_ids):
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.ANSWER_CANDIDATE_MISMATCH
        )

    for place_id in selected_ids:
        candidate = candidates_by_id[place_id]
        if candidate.congestion.status != "available" and _mentions_quietness(
            reasons[place_id]
        ):
            raise AttractionPredictionValidationError(
                AttractionFallbackReason.UNSUPPORTED_QUIETNESS_CLAIM
            )
    if any(
        candidates_by_id[place_id].congestion.status != "available"
        for place_id in selected_ids
    ) and _mentions_quietness(answer):
        raise AttractionPredictionValidationError(
            AttractionFallbackReason.UNSUPPORTED_QUIETNESS_CLAIM
        )

    return AttractionAnswerResult(
        answer=answer.strip(),
        selections=[
            AttractionSelection(
                place_id=place_id,
                selection_reason=reasons[place_id].strip(),
            )
            for place_id in selected_ids
        ],
    )


def fallback_attraction_answer(
    answer_input: AttractionAnswerInput,
) -> AttractionAnswerResult:
    """LLM 결과와 무관하게 재랭킹 상위 후보를 안전하게 반환한다."""

    selected = sorted(
        answer_input.candidates,
        key=lambda candidate: candidate.rank,
    )[:settings.attraction_recommendation_limit]
    english = answer_input.language.casefold().startswith("en")
    if english:
        reason = (
            "Selected using verified attraction information that matches "
            "your request."
        )
        answer = (
            "Here are verified attraction recommendations matching your request: "
            + ", ".join(candidate.name for candidate in selected)
            + "."
            if selected
            else "No verified attraction candidates are available."
        )
    else:
        reason = "관광지 관련 검증 정보와 요청 조건을 바탕으로 선정했습니다."
        answer = (
            "요청 조건에 맞는 검증된 관광지 추천은 "
            + ", ".join(candidate.name for candidate in selected)
            + "입니다."
            if selected
            else "검증된 관광지 후보가 없습니다."
        )
    return AttractionAnswerResult(
        answer=answer,
        selections=[
            AttractionSelection(
                place_id=candidate.place_id,
                selection_reason=reason,
            )
            for candidate in selected
        ],
        used_fallback=True,
    )


def _mentions_quietness(text: str) -> bool:
    normalized = text.casefold()
    return any(term in normalized for term in _QUIETNESS_TERMS)


def _unique_candidate_ids_by_name(
    answer_input: AttractionAnswerInput,
) -> dict[str, str]:
    """DSPy가 ID 대신 정확한 후보명을 재출력한 경우만 안전하게 복구한다."""

    grouped: dict[str, list[str]] = {}
    for candidate in answer_input.candidates:
        normalized = _normalize_reference(candidate.name)
        if normalized:
            grouped.setdefault(normalized, []).append(candidate.place_id)
    return {
        name: place_ids[0]
        for name, place_ids in grouped.items()
        if len(place_ids) == 1
    }


def _resolve_candidate_id(
    reference: str,
    candidates_by_id: dict[str, Any],
    candidate_ids_by_name: dict[str, str],
) -> str | None:
    value = reference.strip()
    if value in candidates_by_id:
        return value
    # 이름은 후보명과 완전히 같고, 그 이름이 후보 안에서 유일할 때만 허용한다.
    return candidate_ids_by_name.get(_normalize_reference(value))


def _normalize_reference(value: str) -> str:
    return " ".join(value.casefold().split())


__all__ = [
    "fallback_attraction_answer",
    "validate_attraction_prediction",
    "validate_attraction_prediction_or_raise",
]
