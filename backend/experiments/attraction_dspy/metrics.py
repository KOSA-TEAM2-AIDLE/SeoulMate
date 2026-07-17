"""관광 후보 선택·답변을 위한 규칙 40% + private judge 60% Hybrid Metric."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import dspy

from experiments.attraction_dspy.dataset import AttractionDspyCase


COMPONENT_WEIGHTS = {
    "selection": 0.40,
    "grounding": 0.25,
    "conditions": 0.15,
    "language_structure": 0.10,
    "clarity": 0.10,
}
RULE_WEIGHT = 0.40
JUDGE_WEIGHT = 0.60
_QUIETNESS_TERMS = (
    "한적",
    "붐비지",
    "덜 붐",
    "혼잡하지",
    "uncrowded",
    "not crowded",
    "less crowded",
    "not busy",
)


class AttractionPrivateJudgeSignature(dspy.Signature):
    """비공개 조건과 공개 근거만으로 선택·답변의 충실도를 평가한다."""

    question: str = dspy.InputField()
    language: str = dspy.InputField()
    candidates_json: str = dspy.InputField()
    required_conditions_json: str = dspy.InputField()
    forbidden_claims_json: str = dspy.InputField()
    selected_place_ids_json: str = dspy.InputField()
    selection_reasons_json: str = dspy.InputField()
    answer: str = dspy.InputField()

    score: int = dspy.OutputField(desc="Overall integer score from 1 to 5")
    hard_fail: bool = dspy.OutputField(
        desc="True for unsupported facts or a supplied forbidden claim"
    )
    reason: str = dspy.OutputField(desc="Brief evidence-grounded assessment")


@dataclass(frozen=True)
class AttractionMetricResult:
    score: float
    rule_score: float
    judge_score: float
    components: dict[str, float]
    component_weights: dict[str, float]
    hard_fail: bool
    hard_fail_reasons: tuple[str, ...]
    judge_reason: str | None = None


def evaluate_attraction_prediction(
    case: AttractionDspyCase,
    prediction: Any,
    *,
    judge=None,
    judge_score: float | None = None,
    judge_hard_fail: bool = False,
) -> AttractionMetricResult:
    public = case.public_input
    private = case.private_label
    candidate_index = {
        candidate.place_id: candidate for candidate in public.candidates
    }
    hard_fail_reasons: list[str] = []

    selected_ids = getattr(prediction, "selected_place_ids", None)
    if not isinstance(selected_ids, list):
        selected_ids = []
        hard_fail_reasons.append("invalid_selection_structure")
    if len(selected_ids) != public.selection_count:
        hard_fail_reasons.append("wrong_selection_count")
    if len(selected_ids) != len(set(selected_ids)):
        hard_fail_reasons.append("duplicate_place_id")
    if any(place_id not in candidate_index for place_id in selected_ids):
        hard_fail_reasons.append("unknown_place_id")

    try:
        reasons = json.loads(getattr(prediction, "selection_reasons_json", ""))
    except (TypeError, json.JSONDecodeError):
        reasons = {}
    if not isinstance(reasons, dict) or set(reasons) != set(selected_ids):
        hard_fail_reasons.append("invalid_selection_reasons")
        reasons = {}
    elif any(not str(reasons[place_id]).strip() for place_id in selected_ids):
        hard_fail_reasons.append("empty_selection_reason")

    answer = str(getattr(prediction, "answer", "") or "").strip()
    combined_text = " ".join(
        [answer, *(str(reasons.get(place_id, "")) for place_id in selected_ids)]
    )
    language_score = _language_score(answer, public.language)
    if language_score == 0.0:
        hard_fail_reasons.append("wrong_answer_language")

    normalized_combined = _normalize(combined_text)
    if any(
        _normalize(claim) and _normalize(claim) in normalized_combined
        for claim in private.forbidden_claims
    ):
        hard_fail_reasons.append("unsupported_or_forbidden_claim")

    selected_candidates = [
        candidate_index[place_id]
        for place_id in selected_ids
        if place_id in candidate_index
    ]
    if any(
        candidate.event_end_date is not None
        and candidate.event_end_date < date.today()
        for candidate in selected_candidates
    ):
        hard_fail_reasons.append("ended_event_selected")
    if any(candidate.congestion is None for candidate in selected_candidates) and any(
        term in combined_text.casefold() for term in _QUIETNESS_TERMS
    ):
        hard_fail_reasons.append("missing_congestion_inference")

    acceptable = set(private.acceptable_place_ids)
    selection_score = (
        sum(place_id in acceptable for place_id in selected_ids)
        / public.selection_count
        if public.selection_count
        else 1.0
    )
    grounding_score = _grounding_score(selected_candidates, reasons)
    conditions_score = _condition_score(combined_text, private.required_conditions)
    structure_score = 1.0 if reasons and answer else 0.0
    language_structure_score = (language_score + structure_score) / 2
    clarity_score = 1.0 if len(answer) >= 20 and all(
        len(str(reasons.get(place_id, "")).strip()) >= 4
        for place_id in selected_ids
    ) else 0.0

    components = {
        "selection": selection_score,
        "grounding": grounding_score,
        "conditions": conditions_score,
        "language_structure": language_structure_score,
        "clarity": clarity_score,
    }
    rule_score = sum(
        components[name] * weight for name, weight in COMPONENT_WEIGHTS.items()
    )

    judge_reason = None
    if judge is not None:
        judged = judge(
            question=public.question,
            language=public.language,
            candidates_json=json.dumps(
                [candidate.model_dump(mode="json") for candidate in public.candidates],
                ensure_ascii=False,
            ),
            required_conditions_json=json.dumps(
                private.required_conditions,
                ensure_ascii=False,
            ),
            forbidden_claims_json=json.dumps(
                private.forbidden_claims,
                ensure_ascii=False,
            ),
            selected_place_ids_json=json.dumps(selected_ids, ensure_ascii=False),
            selection_reasons_json=json.dumps(reasons, ensure_ascii=False),
            answer=answer,
        )
        raw_score = float(getattr(judged, "score", 1))
        judge_score = max(0.0, min(1.0, raw_score / 5.0))
        judge_hard_fail = judge_hard_fail or bool(
            getattr(judged, "hard_fail", False)
        )
        judge_reason = str(getattr(judged, "reason", "") or "") or None
    effective_judge_score = max(0.0, min(1.0, float(judge_score or 0.0)))
    if judge_hard_fail:
        hard_fail_reasons.append("private_judge_hard_fail")

    unique_hard_fails = tuple(dict.fromkeys(hard_fail_reasons))
    hard_fail = bool(unique_hard_fails)
    score = 0.0 if hard_fail else (
        RULE_WEIGHT * rule_score + JUDGE_WEIGHT * effective_judge_score
    )
    return AttractionMetricResult(
        score=score,
        rule_score=rule_score,
        judge_score=effective_judge_score,
        components=components,
        component_weights=dict(COMPONENT_WEIGHTS),
        hard_fail=hard_fail,
        hard_fail_reasons=unique_hard_fails,
        judge_reason=judge_reason,
    )


def build_optimization_metric(
    case_index: dict[str, AttractionDspyCase],
    *,
    judge=None,
):
    """MIPROv2에는 public Example만 주고 private label은 closure에서만 참조한다."""

    private_judge = judge or dspy.Predict(AttractionPrivateJudgeSignature)

    def metric(example, prediction, trace=None) -> float:
        case_id = str(getattr(example, "case_id", ""))
        try:
            case = case_index[case_id]
        except KeyError as error:
            raise ValueError(f"등록되지 않은 평가 case_id입니다: {case_id}") from error
        return evaluate_attraction_prediction(
            case,
            prediction,
            judge=private_judge,
        ).score

    return metric


def _grounding_score(candidates, reasons: dict[str, Any]) -> float:
    if not candidates:
        return 0.0
    grounded = 0
    for candidate in candidates:
        evidence = " ".join(
            filter(
                None,
                [
                    candidate.name,
                    candidate.category,
                    candidate.description,
                    *candidate.reviews,
                    candidate.congestion,
                ],
            )
        )
        evidence_terms = {
            term for term in re.findall(r"[0-9A-Za-z가-힣]+", evidence.casefold())
            if len(term) >= 2
        }
        reason = str(reasons.get(candidate.place_id, "")).casefold()
        grounded += any(term in reason for term in evidence_terms)
    return grounded / len(candidates)


def _condition_score(text: str, conditions: list[str]) -> float:
    if not conditions:
        return 1.0
    normalized = _normalize(text)
    return sum(_normalize(condition) in normalized for condition in conditions) / len(
        conditions
    )


def _language_score(text: str, language: str) -> float:
    hangul = len(re.findall(r"[가-힣]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if language.casefold().startswith("ko"):
        return 1.0 if hangul >= 5 else 0.0
    if language.casefold().startswith("en"):
        return 1.0 if latin >= 10 and latin > hangul else 0.0
    return 1.0 if text else 0.0


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").casefold())


__all__ = [
    "AttractionMetricResult",
    "AttractionPrivateJudgeSignature",
    "COMPONENT_WEIGHTS",
    "build_optimization_metric",
    "evaluate_attraction_prediction",
]
