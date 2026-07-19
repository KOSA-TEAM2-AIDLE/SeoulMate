"""Draft evidence-specific questions for pending augmentation cases only."""

from __future__ import annotations

import json
from pathlib import Path

import dspy

from core.config import settings


class AugmentationQuestionSignature(dspy.Signature):
    """Create one concise question whose answer is the target candidate from supplied evidence."""

    language: str = dspy.InputField()
    candidates_json: str = dspy.InputField()
    target_place_id: str = dspy.InputField()
    question: str = dspy.OutputField(
        desc="Question only; use a factual discriminator from target evidence and never write a place name."
    )


def main() -> int:
    path = Path(__file__).parents[2] / "data" / "attraction" / "DSPy" / "augmentation_draft" / "augmentation_draft.jsonl"
    key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    lm = dspy.LM(settings.attraction_dspy_model, api_key=key, temperature=0, max_tokens=180)
    with dspy.context(lm=lm):
        draft = dspy.Predict(AugmentationQuestionSignature)
        for row in rows:
            target = (row["expected"]["selected_place_ids"] or [None])[0]
            if target is None:
                row["input"]["question"] = (
                    "모든 후보가 조건과 충돌하면 추천할 곳이 없다고 알려줘"
                    if row["input"]["language"] == "ko"
                    else "Say there is no match if every candidate conflicts with the condition."
                )
            else:
                prediction = draft(
                    language=row["input"]["language"],
                    candidates_json=json.dumps(row["input"]["candidates"], ensure_ascii=False),
                    target_place_id=target,
                )
                row["input"]["question"] = prediction.question.strip()
            row["review_status"] = "pending"
            row["review_notes"] = "Question drafted from isolated candidate evidence; human review required before train/dev use."
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
