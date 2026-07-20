"""Build a verified attraction answer without asking the LLM to reproduce evidence."""

from __future__ import annotations

from typing import Any

from domains.attraction.answer_models import AttractionAnswerInput
from domains.attraction.dspy.contracts import AttractionReasonPrediction


def hydrate_structured_answer(
    answer_input: AttractionAnswerInput,
    selected_place_ids: list[str],
    reason_prediction: AttractionReasonPrediction,
) -> dict[str, Any]:
    candidates = {candidate.place_id: candidate for candidate in answer_input.candidates}
    recommendations = []
    for place_id in selected_place_ids:
        candidate = candidates[place_id]
        review = next((item for item in candidate.reviews if item.strip()), None)
        recommendations.append({
            "place_id": candidate.place_id,
            "name": candidate.name,
            "recommendation_reason": reason_prediction.recommendation_reasons[place_id],
            "description_evidence": [candidate.description] if candidate.description else [],
            "review_evidence": [review] if review else [],
            "congestion": candidate.congestion.model_dump(),
            "weather": candidate.weather.model_dump(),
        })
    no_result_reason = None
    if not recommendations:
        no_result_reason = (
            "No verified attraction candidates match the request."
            if answer_input.language.casefold().startswith("en")
            else "요청 조건에 맞는 검증된 관광지 후보가 없습니다."
        )
    return {
        "language": answer_input.language,
        "recommendations": recommendations,
        "no_result_reason": no_result_reason,
    }


__all__ = ["hydrate_structured_answer"]
