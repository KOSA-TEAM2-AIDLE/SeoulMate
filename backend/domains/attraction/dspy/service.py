"""All-or-nothing runtime boundary for split attraction DSPy artifacts."""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import dspy

from core.config import settings
from domains.attraction.answer_models import AttractionAnswerInput
from domains.attraction.dspy.renderer import render_selection_result
from domains.attraction.dspy.grounding import ground_structured_answer
from domains.attraction.dspy.programs import TourismAnswerProgram, TourismSelectionProgram
from domains.attraction.dspy.validator import (
    validate_selection_prediction,
    validate_structured_answer,
)


class AttractionDspyRuntimeService:
    """Runs split artifacts or returns the supplied safe fallback."""

    def __init__(
        self,
        *,
        artifact_loader: Callable[[], Any],
        fallback: Callable[[AttractionAnswerInput], Any],
    ) -> None:
        self._artifact_loader = artifact_loader
        self._fallback = fallback

    def run(self, answer_input: AttractionAnswerInput) -> Any:
        try:
            runtime = self._artifact_loader()
        except Exception:
            return self._fallback(answer_input)
        return runtime.run(answer_input)


class SplitAttractionDspyRuntime:
    """Execute independently optimized selection and answer artifacts."""

    def __init__(
        self,
        *,
        selection_program: Any,
        answer_program: Any,
        lm: Any,
    ) -> None:
        self._selection_program = selection_program
        self._answer_program = answer_program
        self._lm = lm

    def run(self, answer_input: AttractionAnswerInput):
        selection_prediction = _invoke(
            self._selection_program,
            self._lm,
            {
                "language": answer_input.language,
                "question": answer_input.question,
                "location": answer_input.location or "",
                "themes_json": json.dumps(answer_input.themes, ensure_ascii=False),
                "selection_count": min(settings.attraction_recommendation_limit, len(answer_input.candidates)),
                "candidates_json": json.dumps(
                    [candidate.model_dump(mode="json") for candidate in answer_input.candidates],
                    ensure_ascii=False,
                ),
            },
        )
        selection = validate_selection_prediction(
            answer_input,
            {
                "selected_place_ids": selection_prediction.selected_place_ids,
                "forbidden_place_ids": selection_prediction.forbidden_place_ids,
                "selection_reasons": json.loads(selection_prediction.selection_reasons_json),
            },
        )
        selected = [
            candidate for candidate in answer_input.candidates
            if candidate.place_id in selection.selected_place_ids
        ]
        answer_prediction = _invoke(
            self._answer_program,
            self._lm,
            {
                "language": answer_input.language,
                "question": answer_input.question,
                "selected_candidates_json": json.dumps(
                    [candidate.model_dump(mode="json") for candidate in selected],
                    ensure_ascii=False,
                ),
                "selection_reasons_json": json.dumps(selection.selection_reasons, ensure_ascii=False),
            },
        )
        answer = validate_structured_answer(
            answer_input,
            selection.selected_place_ids,
            ground_structured_answer(
                answer_input,
                selection.selected_place_ids,
                selection.selection_reasons,
                json.loads(answer_prediction.structured_answer_json),
            ),
        )
        return render_selection_result(
            selection,
            answer,
            question=answer_input.question,
        )


def load_split_attraction_runtime(
    selection_path: str | Path | None = None,
    answer_path: str | Path | None = None,
) -> SplitAttractionDspyRuntime:
    """Load both offline artifacts; callers retain the legacy DSPy fallback on error."""

    selection_path = Path(selection_path or settings.attraction_dspy_selection_artifact_path)
    answer_path = Path(answer_path or settings.attraction_dspy_answer_artifact_path)
    if not selection_path.is_file() or not answer_path.is_file():
        raise FileNotFoundError("분리 관광 DSPy artifact가 아직 준비되지 않았습니다.")
    selection_program = TourismSelectionProgram()
    answer_program = TourismAnswerProgram()
    selection_program.load(str(selection_path))
    answer_program.load(str(answer_path))
    api_key = (
        settings.openai_api_key.get_secret_value().strip()
        if settings.openai_api_key is not None
        else ""
    )
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 없어 관광 DSPy를 호출할 수 없습니다.")
    return SplitAttractionDspyRuntime(
        selection_program=selection_program,
        answer_program=answer_program,
        lm=dspy.LM(
            settings.attraction_dspy_model,
            api_key=api_key,
            temperature=settings.attraction_dspy_temperature,
            max_tokens=settings.attraction_dspy_max_tokens,
        ),
    )


def _invoke(program: Any, lm: Any, inputs: dict[str, Any]):
    if lm is None:
        return program(**inputs)
    with dspy.context(lm=lm):
        return program(**inputs)


__all__ = [
    "AttractionDspyRuntimeService",
    "SplitAttractionDspyRuntime",
    "load_split_attraction_runtime",
]
