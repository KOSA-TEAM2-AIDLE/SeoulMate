"""검증된 관광 후보를 DSPy 선택 결과로 변환하는 도메인 경계."""

from __future__ import annotations

from core.config import settings
from application.recommendation.selection_models import (
    CandidateSelection,
    CandidateSelectionResult,
)
from domains.attraction.answer_evidence import build_attraction_answer_input
from domains.attraction.answer_generator import AttractionAnswerGenerator
from domains.attraction.answer_models import AttractionAnswerResult
from domains.attraction.answer_validation import fallback_attraction_answer
from domains.attraction.value_normalization import optional_text
from domains.common.models import DomainSearchRequest, SearchCandidate


class AttractionSelectionService:
    """DSPy는 ID·이유·답변만 만들고 원본 후보 사실은 변경하지 않는다."""

    domain = "attraction"

    def __init__(self, *, answer_generator=None) -> None:
        self._answer_generator = answer_generator or AttractionAnswerGenerator()

    async def select(
        self,
        request: DomainSearchRequest,
        candidates: list[SearchCandidate],
    ) -> CandidateSelectionResult:
        if request.domain != self.domain:
            raise ValueError(
                f"관광 도메인 요청이 아닙니다: {request.domain}"
            )

        ranked = sorted(
            candidates,
            key=lambda candidate: candidate.final_score,
            reverse=True,
        )[:10]
        try:
            answer = await self._answer_generator.generate(
                question=request.search_query,
                language=request.language,
                location=request.location or request.current_location_name,
                themes=request.themes,
                candidates=ranked,
            )
        except Exception:
            return self._raw_ranked_fallback(request, ranked)
        if not self._is_safe_selection(answer, ranked):
            answer = self._fallback(request, ranked)
        return self._to_common_result(answer)

    @staticmethod
    def _is_safe_selection(
        answer: AttractionAnswerResult,
        candidates: list[SearchCandidate],
    ) -> bool:
        expected_count = min(
            settings.attraction_recommendation_limit,
            len(candidates),
        )
        selected_ids = [selection.place_id for selection in answer.selections]
        allowed_ids = {candidate.place_id for candidate in candidates}
        return (
            len(selected_ids) == expected_count
            and len(selected_ids) == len(set(selected_ids))
            and all(place_id in allowed_ids for place_id in selected_ids)
        )

    @staticmethod
    def _fallback(
        request: DomainSearchRequest,
        candidates: list[SearchCandidate],
    ) -> AttractionAnswerResult:
        answer_input = build_attraction_answer_input(
            question=request.search_query,
            language=request.language,
            location=request.location or request.current_location_name,
            themes=request.themes,
            candidates=candidates,
        )
        return fallback_attraction_answer(answer_input)

    @staticmethod
    def _to_common_result(
        answer: AttractionAnswerResult,
    ) -> CandidateSelectionResult:
        return CandidateSelectionResult(
            answer=answer.answer,
            selections=[
                CandidateSelection(
                    place_id=selection.place_id,
                    selection_reason=selection.selection_reason,
                )
                for selection in answer.selections
            ],
            used_fallback=answer.used_fallback,
        )

    @staticmethod
    def _raw_ranked_fallback(
        request: DomainSearchRequest,
        candidates: list[SearchCandidate],
    ) -> CandidateSelectionResult:
        valid = [
            candidate
            for candidate in candidates
            if optional_text(candidate.place_id) is not None
            and optional_text(candidate.name) is not None
            and optional_text(candidate.category) is not None
        ][:settings.attraction_recommendation_limit]
        english = request.language.casefold().startswith("en")
        if english:
            reason = "Selected from the highest-ranked verified search results."
            answer = (
                "Here are the highest-ranked verified results: "
                + ", ".join(candidate.name.strip() for candidate in valid)
                + "."
                if valid
                else "No verified attraction candidates are available."
            )
        else:
            reason = "검증된 검색 결과에서 상위 후보로 선정했습니다."
            answer = (
                "검증된 검색 상위 결과는 "
                + ", ".join(candidate.name.strip() for candidate in valid)
                + "입니다."
                if valid
                else "검증된 관광지 후보가 없습니다."
            )
        return CandidateSelectionResult(
            answer=answer,
            selections=[
                CandidateSelection(
                    place_id=candidate.place_id.strip(),
                    selection_reason=reason,
                )
                for candidate in valid
            ],
            used_fallback=True,
        )


__all__ = ["AttractionSelectionService"]
