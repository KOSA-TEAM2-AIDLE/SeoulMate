"""관광지·행사 후보 선정과 답변 생성을 위한 DSPy Program."""

from __future__ import annotations

import json
from pathlib import Path

import dspy

from core.config import settings


class AttractionProgramArtifactError(ValueError):
    """최적화 Program artifact를 복원할 수 없을 때 발생한다."""


class AttractionSelectionAnswerSignature(dspy.Signature):
    """
    주어진 관광지·행사 후보 안에서만 질문에 가장 잘 맞는 장소를 선택하고 답변한다.

    답변과 선정 이유는 사용자의 언어와 일치해야 한다. 후보에 제공된 근거만 사용하고,
    요금·운영시간·거리·행사 기간·리뷰를 추측하지 말아야 한다. 혼잡도는 공식 POI 구역의 관측값이며
    시설 내부 인파로 확정하지 말아야 한다. 혼잡도 근거가 없으면 한적함을 추론하거나 선정 근거로 사용하지 말아야 한다.
    weather가 없는 후보에는 날씨 적합성을 추론하지 말고, weather에 명시된
    관측값과 실내·실외 문서 근거만 사용한다.
    각 후보의 constraints는 상위 파서가 분리한 required/excluded 조건과 문서 일치
    근거다. unknown은 적합하다는 뜻이 아니며, 원문 질문과 후보 근거로만 판단해야 한다.
    selection_count는 최대 선택 개수다. selected_place_ids에는 조건을 만족하는
    고유한 후보 ID를 0개부터 selection_count개까지 순서대로 반환한다.
    모든 후보가 명시적 제외 조건에 충돌하거나 근거로 적합성을 판단할 수
    없으면 0개와 조건에 맞는 후보가 없다는 답변을 반환한다.
    selection_reasons_json은 선택한 ID를 key, 근거 기반 선정 이유를 value로 갖는 JSON object 문자열이어야 한다.
    """

    language: str = dspy.InputField(desc="Answer language such as ko or en")
    question: str = dspy.InputField(desc="Original user question")
    location: str = dspy.InputField(desc="Resolved location or an empty string")
    themes_json: str = dspy.InputField(desc="Requested themes as a JSON array")
    selection_count: int = dspy.InputField(desc="Maximum number of candidates to select; zero is valid")
    candidates_json: str = dspy.InputField(desc="Only verified candidate evidence allowed")

    selected_place_ids: list[str] = dspy.OutputField(
        desc="Unique selected candidate IDs in recommendation order"
    )
    selection_reasons_json: str = dspy.OutputField(
        desc="JSON object mapping every selected ID to its grounded reason"
    )
    answer: str = dspy.OutputField(
        desc="Concise final answer grounded in candidates and written in language"
    )


class AttractionSelectionAnswerProgram(dspy.Module):
    """최적화 전·후에 동일한 입출력 계약을 제공하는 Program."""

    def __init__(self) -> None:
        super().__init__()
        self.generate = dspy.Predict(AttractionSelectionAnswerSignature)

    def forward(
        self,
        *,
        language: str,
        question: str,
        location: str,
        themes_json: str,
        selection_count: int,
        candidates_json: str,
    ):
        return self.generate(
            language=language,
            question=question,
            location=location,
            themes_json=themes_json,
            selection_count=selection_count,
            candidates_json=candidates_json,
        )


def load_attraction_program(
    artifact_path: str | Path | None = None,
) -> AttractionSelectionAnswerProgram:
    """오프라인에서 생성한 artifact만 읽고 최적화은 실행하지 않는다."""

    path = Path(artifact_path or settings.attraction_dspy_artifact_path)
    if not path.is_file():
        raise FileNotFoundError(f"관광 DSPy artifact를 찾을 수 없습니다: {path}")

    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise ValueError("artifact 최상위는 JSON object여야 합니다.")
        program = AttractionSelectionAnswerProgram()
        program.load(str(path))
    except Exception as error:
        raise AttractionProgramArtifactError(
            f"관광 DSPy artifact를 불러오지 못했습니다: {path}"
        ) from error
    return program


__all__ = [
    "AttractionProgramArtifactError",
    "AttractionSelectionAnswerProgram",
    "AttractionSelectionAnswerSignature",
    "load_attraction_program",
]
