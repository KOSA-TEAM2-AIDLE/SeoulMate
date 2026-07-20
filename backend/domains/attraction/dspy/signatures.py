"""DSPy signatures for independent attraction selection and answer steps."""

import dspy


class TourismSelectionSignature(dspy.Signature):
    """Choose only verified attraction candidates and return JSON-compatible IDs."""

    language: str = dspy.InputField()
    question: str = dspy.InputField()
    location: str = dspy.InputField()
    themes_json: str = dspy.InputField()
    selection_count: int = dspy.InputField()
    candidates_json: str = dspy.InputField()

    selected_place_ids: list[str] = dspy.OutputField(
        desc="JSON list of unique selected candidate place_id values, at most selection_count"
    )
    forbidden_place_ids: list[str] = dspy.OutputField(
        desc="JSON list of candidate place_id values excluded by explicit constraints"
    )
    selection_reasons_json: str = dspy.OutputField(
        desc=(
            "A valid JSON object string only: every selected place_id is a key and "
            "its grounded recommendation reason is the non-empty string value. "
            "Do not return prose, Markdown, or a JSON string."
        )
    )


class TourismAnswerSignature(dspy.Signature):
    """Write a structured answer for validated candidates. Evidence arrays must contain
    only non-empty verbatim substrings copied exactly from the matching candidate
    description or review. Include at most one short excerpt per evidence field; use an
    empty array when that source is unavailable. Never summarize, translate, paraphrase,
    or invent evidence.
    """

    language: str = dspy.InputField()
    question: str = dspy.InputField()
    selected_candidates_json: str = dspy.InputField()
    selection_reasons_json: str = dspy.InputField()

    structured_answer_json: str = dspy.OutputField(
        desc=(
            "A valid JSON object string only, with exactly language, recommendations, "
            "and no_result_reason keys. recommendations is a list (at most 3) whose "
            "items contain place_id, name, recommendation_reason, description_evidence, "
            "review_evidence, congestion, weather, and optional visitor_note. Each "
            "description_evidence and review_evidence value must be copied verbatim from "
            "the matching selected candidate input. Include at most one short excerpt per "
            "evidence field, or [] when unavailable; never summarize or paraphrase it. Each "
            "congestion/weather object must have status available|unavailable; unavailable "
            "must contain no value/basis/observed_at. Use only selected candidate evidence. "
            "Do not return prose, Markdown, or another JSON shape."
        )
    )


class TourismReasonSignature(dspy.Signature):
    """Write one concise recommendation reason for every selected candidate.
    Return only a JSON object that maps each selected place_id to a non-empty reason.
    """

    language: str = dspy.InputField()
    question: str = dspy.InputField()
    selected_candidates_json: str = dspy.InputField()
    selection_reasons_json: str = dspy.InputField()

    recommendation_reasons_json: str = dspy.OutputField(
        desc="JSON object with exactly every selected place_id as a key and one non-empty recommendation reason as its value."
    )


__all__ = ["TourismAnswerSignature", "TourismReasonSignature", "TourismSelectionSignature"]
