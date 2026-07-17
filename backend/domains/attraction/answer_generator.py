"""관광 DSPy Program을 호출하는 비동기 운영 진입점."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import dspy

from core.config import settings
from domains.attraction.answer_evidence import build_attraction_answer_input
from domains.attraction.answer_models import AttractionAnswerResult
from domains.attraction.answer_program import load_attraction_program
from domains.attraction.answer_validation import (
    fallback_attraction_answer,
    validate_attraction_prediction,
)
from domains.common.models import SearchCandidate


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
        try:
            program = self._program_loader()
            lm = self._lm_factory()
            prediction = await asyncio.wait_for(
                asyncio.to_thread(_invoke_program, program, lm, program_inputs),
                timeout=self._timeout_seconds,
            )
        except Exception:
            return fallback_attraction_answer(answer_input)
        return validate_attraction_prediction(answer_input, prediction)


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


__all__ = ["AttractionAnswerGenerator"]
