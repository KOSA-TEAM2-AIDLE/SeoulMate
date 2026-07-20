"""검증된 관광 후보를 DSPy 선택 결과로 변환하는 도메인 경계."""

from __future__ import annotations

import asyncio
import logging
from time import perf_counter

from core.config import settings
from application.recommendation.selection_models import (
    CandidateSelection,
    CandidateSelectionResult,
)
from domains.attraction.answer_evidence import build_attraction_answer_input
from domains.attraction.answer_generator import AttractionAnswerGenerator
from domains.attraction.answer_models import AttractionAnswerResult
from domains.attraction.answer_validation import fallback_attraction_answer
from domains.attraction.dspy.service import load_split_attraction_runtime
from domains.attraction.value_normalization import optional_text
from domains.common.models import DomainSearchRequest, SearchCandidate


logger = logging.getLogger(__name__)


class AttractionSelectionService:
    """DSPy는 ID·이유·답변만 만들고 원본 후보 사실은 변경하지 않는다."""

    domain = "attraction"

    def __init__(
        self,
        *,
        answer_generator=None,
        dspy_runtime=None,
        split_timeout_seconds: float | None = None,
    ) -> None:
        self._answer_generator = answer_generator or AttractionAnswerGenerator()
        self._dspy_runtime = (
            dspy_runtime
            if dspy_runtime is not None
            else (None if answer_generator is not None else _LazySplitRuntime())
        )
        self._split_timeout_seconds = (
            settings.attraction_dspy_split_timeout_seconds
            if split_timeout_seconds is None
            else split_timeout_seconds
        )
        if self._split_timeout_seconds <= 0:
            raise ValueError("split_timeout_seconds는 양수여야 합니다.")

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
        question = _original_question(request)
        if self._dspy_runtime is not None:
            started = perf_counter()
            try:
                answer_input = build_attraction_answer_input(
                    question=question,
                    language=request.language,
                    location=request.location or request.current_location_name,
                    themes=request.themes,
                    candidates=ranked,
                )
                result = await _run_split_runtime(
                    self._dspy_runtime,
                    answer_input,
                    timeout_seconds=self._split_timeout_seconds,
                )
                if not isinstance(result, CandidateSelectionResult):
                    raise TypeError("split runtime이 CandidateSelectionResult를 반환하지 않았습니다.")
                return result
            except Exception as error:
                _log_split_fallback(
                    error=error,
                    elapsed_ms=round((perf_counter() - started) * 1000),
                    candidate_count=len(ranked),
                )
        try:
            answer = await self._answer_generator.generate(
                question=question,
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
            len(selected_ids) <= expected_count
            and len(selected_ids) == len(set(selected_ids))
            and all(place_id in allowed_ids for place_id in selected_ids)
        )

    @staticmethod
    def _fallback(
        request: DomainSearchRequest,
        candidates: list[SearchCandidate],
    ) -> AttractionAnswerResult:
        answer_input = build_attraction_answer_input(
            question=_original_question(request),
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


def _original_question(request: DomainSearchRequest) -> str:
    parsed_query = request.context.get("parsed_query")
    return (
        getattr(parsed_query, "original_question", None)
        or (
            parsed_query.get("original_question")
            if isinstance(parsed_query, dict)
            else None
        )
        or request.search_query
    )


async def _run_split_runtime(
    runtime,
    answer_input,
    *,
    timeout_seconds: float,
) -> CandidateSelectionResult:
    return await asyncio.wait_for(
        asyncio.to_thread(runtime.run, answer_input),
        timeout=timeout_seconds,
    )


def _log_split_fallback(
    *,
    error: Exception,
    elapsed_ms: int,
    candidate_count: int,
) -> None:
    logger.warning(
        "attraction_dspy_split_fallback stage=split_runtime "
        "error_type=%s elapsed_ms=%s candidate_count=%s",
        type(error).__name__,
        elapsed_ms,
        candidate_count,
    )


__all__ = ["AttractionSelectionService"]


class _LazySplitRuntime:
    """Avoid artifact/LM work until a real attraction request reaches the selector."""

    def __init__(self) -> None:
        self._runtime = None

    def run(self, answer_input):
        if self._runtime is None:
            self._runtime = load_split_attraction_runtime()
        return self._runtime.run(answer_input)
