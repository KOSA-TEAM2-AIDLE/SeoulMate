"""관광 DSPy Program을 호출하는 비동기 운영 진입점."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import dspy

from core.config import settings
from domains.attraction.answer_evidence import build_attraction_answer_input
from domains.attraction.answer_diagnostics import (
    AttractionFallbackReason,
    AttractionPredictionValidationError,
)
from domains.attraction.answer_models import AttractionAnswerResult
from domains.attraction.answer_program import load_attraction_program
from domains.attraction.answer_validation import (
    fallback_attraction_answer,
    validate_attraction_prediction_or_raise,
)
from domains.common.models import SearchCandidate


logger = logging.getLogger(__name__)


class AttractionAnswerGenerator:
    """재랭킹 후보를 DSPy로 선택하고 예외 시 안전하게 fallback한다."""

    def __init__(
        self,
        *,
        program_loader: Callable[[], Any] = load_attraction_program,
        lm_factory: Callable[[], Any] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 양수여야 합니다.")
        self._program_loader = program_loader
        self._lm_factory = lm_factory or _build_lm
        self._timeout_seconds = timeout_seconds

    async def generate(
        self,
        *,
        question: str,
        language: str,
        location: str | None,
        themes: list[str],
        candidates: list[SearchCandidate],
    ) -> AttractionAnswerResult:
        answer_input = build_attraction_answer_input(
            question=question,
            language=language,
            location=location,
            themes=themes,
            candidates=candidates,
        )
        program_inputs = {
            "language": answer_input.language,
            "question": answer_input.question,
            "location": answer_input.location or "",
            "themes_json": json.dumps(answer_input.themes, ensure_ascii=False),
            "selection_count": min(
                settings.attraction_recommendation_limit,
                len(answer_input.candidates),
            ),
            "candidates_json": json.dumps(
                [
                    candidate.model_dump(mode="json")
                    for candidate in answer_input.candidates
                ],
                ensure_ascii=False,
            ),
        }
        # 로더 실패는 artifact 경로·파일·DSPy 버전 문제를 의미한다.
        try:
            program = self._program_loader()
        except Exception as error:
            _log_fallback(
                stage="program_load",
                reason=AttractionFallbackReason.ARTIFACT_LOAD_FAILED,
                error=error,
                candidate_count=len(answer_input.candidates),
            )
            return fallback_attraction_answer(answer_input)

        # LM 구성 실패는 주로 API 키나 모델 설정 문제를 의미한다.
        try:
            lm = self._lm_factory()
        except Exception as error:
            _log_fallback(
                stage="lm_configuration",
                reason=AttractionFallbackReason.LM_CONFIGURATION_FAILED,
                error=error,
                candidate_count=len(answer_input.candidates),
            )
            return fallback_attraction_answer(answer_input)

        try:
            prediction = await asyncio.wait_for(
                asyncio.to_thread(_invoke_program, program, lm, program_inputs),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as error:
            _log_fallback(
                stage="model_call",
                reason=AttractionFallbackReason.LM_TIMEOUT,
                error=error,
                candidate_count=len(answer_input.candidates),
            )
            return fallback_attraction_answer(answer_input)
        except Exception as error:
            _log_fallback(
                stage="model_call",
                reason=AttractionFallbackReason.LM_CALL_FAILED,
                error=error,
                candidate_count=len(answer_input.candidates),
            )
            return fallback_attraction_answer(answer_input)

        # 호출은 성공했지만 ID·이유 JSON·근거 계약을 어겼을 때의 진단이다.
        try:
            return validate_attraction_prediction_or_raise(
                answer_input,
                prediction,
            )
        except AttractionPredictionValidationError as error:
            _log_fallback(
                stage="prediction_validation",
                reason=error.reason,
                error=error,
                candidate_count=len(answer_input.candidates),
                selected_count=_safe_selected_count(prediction),
            )
            return fallback_attraction_answer(answer_input)


def _build_lm():
    api_key = (
        settings.openai_api_key.get_secret_value().strip()
        if settings.openai_api_key is not None
        else ""
    )
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 없어 관광 DSPy를 호출할 수 없습니다.")
    return dspy.LM(
        settings.attraction_dspy_model,
        api_key=api_key,
        temperature=settings.attraction_dspy_temperature,
        max_tokens=settings.attraction_dspy_max_tokens,
    )


def _invoke_program(program: Any, lm: Any, inputs: dict[str, Any]):
    if lm is None:
        return program(**inputs)
    with dspy.context(lm=lm):
        return program(**inputs)


def _safe_selected_count(prediction: Any) -> int | None:
    selected = getattr(prediction, "selected_place_ids", None)
    return len(selected) if isinstance(selected, list) else None


def _log_fallback(
    *,
    stage: str,
    reason: AttractionFallbackReason,
    error: Exception,
    candidate_count: int,
    selected_count: int | None = None,
) -> None:
    # 예외 메시지에 외부 응답이 섞일 수 있어 타입만 기록한다.
    logger.warning(
        "attraction_dspy_fallback stage=%s reason=%s error_type=%s "
        "candidate_count=%s selected_count=%s",
        stage,
        reason.value,
        type(error).__name__,
        candidate_count,
        selected_count,
    )
__all__ = ["AttractionAnswerGenerator"]
