"""Draft reviewable, evidence-specific questions for gold cases without training on them."""

from __future__ import annotations

import json
from pathlib import Path

import dspy

from core.config import settings


class GoldQuestionSignature(dspy.Signature):
    """Create one concise user question that selects the target only from supplied evidence."""

    language: str = dspy.InputField()
    candidates_json: str = dspy.InputField()
    target_place_id: str = dspy.InputField()
    question: str = dspy.OutputField(desc="Question only; include a factual discriminator from target evidence, never a place name")


def main() -> int:
    path = Path(__file__).parents[2] / "data" / "attraction" / "DSPy" / "gold_test" / "gold_test.jsonl"
    key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")
    lm = dspy.LM(settings.attraction_dspy_model, api_key=key, temperature=0, max_tokens=180)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    with dspy.context(lm=lm):
        draft = dspy.Predict(GoldQuestionSignature)
        for row in rows:
            target = (row["expected"]["selected_place_ids"] or [None])[0]
            if target is None:
                row["input"]["question"] = "조건에 맞는 후보가 없으면 없다고 알려줘" if row["input"]["language"] == "ko" else "Say there is no match if every candidate conflicts with the condition."
            else:
                prediction = draft(language=row["input"]["language"], candidates_json=json.dumps(row["input"]["candidates"], ensure_ascii=False), target_place_id=target)
                row["input"]["question"] = prediction.question.strip()
            row["review_status"] = "pending"
            row["review_notes"] = "Question drafted from candidate evidence; human review required before benchmark use."
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
