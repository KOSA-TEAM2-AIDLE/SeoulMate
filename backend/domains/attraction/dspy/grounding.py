"""Replace model-generated attraction facts with verified candidate and MCP context."""

from __future__ import annotations

from typing import Any

from domains.attraction.answer_models import AttractionAnswerInput
from domains.attraction.dspy.validator import AttractionDspyValidationError


def ground_structured_answer(
    answer_input: AttractionAnswerInput,
    selected_place_ids: list[str],
    selection_reasons: dict[str, str],
    raw_answer: Any,
) -> dict[str, Any]:
    if not isinstance(raw_answer, dict):
        raise AttractionDspyValidationError("잘못된 Answer DSPy 출력입니다.")
    candidates = {candidate.place_id: candidate for candidate in answer_input.candidates}
    model_reasons = {
        str(item.get("place_id")): item.get("recommendation_reason")
        for item in raw_answer.get("recommendations", [])
        if isinstance(item, dict)
    }
    recommendations = []
    for place_id in selected_place_ids:
        candidate = candidates.get(place_id)
        if candidate is None:
            raise AttractionDspyValidationError("선택 ID가 입력 후보에 없습니다.")
        reason = str(model_reasons.get(place_id) or selection_reasons.get(place_id) or "").strip()
        if not reason:
            raise AttractionDspyValidationError("추천 사유가 비어 있습니다.")
        review = next((value for value in candidate.reviews if value.strip()), None)
        recommendations.append({
            "place_id": candidate.place_id,
            "name": candidate.name,
            "recommendation_reason": reason,
            "description_evidence": [candidate.description] if candidate.description else [],
            "review_evidence": [review] if review else [],
            "congestion": candidate.congestion.model_dump(),
            "weather": candidate.weather.model_dump(),
        })
    return {
        "language": answer_input.language,
        "recommendations": recommendations,
        "no_result_reason": None,
    }


__all__ = ["ground_structured_answer"]
