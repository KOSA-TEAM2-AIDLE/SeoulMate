"""DSPy 예측을 검증하고 안전한 정적 fallback을 제공한다."""

from __future__ import annotations

import json
from typing import Any

from core.config import settings
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
        selected_ids = prediction.selected_place_ids
        if not isinstance(selected_ids, list) or not all(
            isinstance(place_id, str) and not is_nullish(place_id)
            for place_id in selected_ids
        ):
            raise ValueError("선택 ID는 비어 있지 않은 문자열 목록이어야 합니다.")

        expected_count = min(
            settings.attraction_recommendation_limit,
            len(answer_input.candidates),
        )
        if len(selected_ids) > expected_count:
            raise ValueError("선택 개수가 최대치를 넘었습니다.")
        if len(selected_ids) != len(set(selected_ids)):
            raise ValueError("선택 ID가 중복됩니다.")

        candidates_by_id = {
            candidate.place_id: candidate for candidate in answer_input.candidates
        }
        if any(place_id not in candidates_by_id for place_id in selected_ids):
            raise ValueError("후보에 없는 ID가 선택됐습니다.")

        reasons = json.loads(prediction.selection_reasons_json)
        if not isinstance(reasons, dict) or set(reasons) != set(selected_ids):
            raise ValueError("선정 이유는 선택 ID와 정확히 일치해야 합니다.")
        if any(
            not isinstance(reasons[place_id], str)
            or is_nullish(reasons[place_id])
            for place_id in selected_ids
        ):
            raise ValueError("선정 이유는 비어 있을 수 없습니다.")

        answer = prediction.answer
        if not isinstance(answer, str) or is_nullish(answer):
            raise ValueError("답변은 비어 있을 수 없습니다.")
        normalized_answer = answer.casefold()
        mentioned_ids = {
            candidate.place_id
            for candidate in answer_input.candidates
            if candidate.name.casefold() in normalized_answer
        }
        if mentioned_ids and mentioned_ids != set(selected_ids):
            raise ValueError("답변의 후보명이 선택 ID와 일치하지 않습니다.")

        for place_id in selected_ids:
            candidate = candidates_by_id[place_id]
            if candidate.congestion is None and _mentions_quietness(
                reasons[place_id]
            ):
                raise ValueError("혼잡도 없이 한적함을 추론했습니다.")
        if any(
            candidates_by_id[place_id].congestion is None
            for place_id in selected_ids
        ) and _mentions_quietness(answer):
            raise ValueError("답변이 혼잡도 없이 한적함을 추론했습니다.")

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
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return fallback_attraction_answer(answer_input)


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
        reason = "Selected from the highest-ranked verified reranking results."
        answer = (
            "Here are the highest-ranked verified results: "
            + ", ".join(candidate.name for candidate in selected)
            + "."
            if selected
            else "No verified attraction candidates are available."
        )
    else:
        reason = "검증된 재랭킹 결과에서 상위 후보로 선정했습니다."
        answer = (
            "검증된 재랭킹 상위 결과는 "
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


__all__ = ["fallback_attraction_answer", "validate_attraction_prediction"]
