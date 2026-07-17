"""구조화된 조건과 관광 후보의 명시적 문서 근거를 비교한다."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from domains.attraction.constraint_normalizer import (
    NormalizedConstraint,
    normalize_constraint_text,
    normalize_constraints,
)
from domains.attraction.repository import AttractionRecord


AssessmentStatus = Literal["match", "conflict", "unknown"]


@dataclass(frozen=True)
class ConstraintAssessment:
    source_text: str
    normalized_text: str
    kind: str
    status: AssessmentStatus
    evidence: tuple[str, ...] = ()


def _candidate_fields(record: AttractionRecord) -> tuple[str, ...]:
    return tuple(
        value
        for value in (
            record.name,
            record.category,
            record.summary,
            record.description,
            record.tags,
            record.hours,
            record.fee,
        )
        if value
    )


def _term_pattern(term: str) -> re.Pattern[str]:
    # 한글 어구의 공백 표기 차이(예: 실탄사격/실탄 사격)는 허용하되,
    # 한 글자 조건은 단어 중간에서 일치(예: 물/박물관)시키지 않는다.
    compact = re.sub(r"\s+", "", term)
    if compact and all("\uac00" <= char <= "\ud7a3" for char in compact):
        body = r"\s*".join(re.escape(char) for char in compact)
        if len(compact) >= 2:
            return re.compile(f"({body})", re.IGNORECASE)
    else:
        body = re.escape(term).replace(r"\ ", r"\s+")
    word = r"0-9a-z\uac00-\ud7a3"
    return re.compile(rf"(?<![{word}])({body})(?![{word}])", re.IGNORECASE)


def find_constraint_evidence(
    constraint_text: str,
    candidate_fields: tuple[str, ...],
) -> tuple[str, ...]:
    term = normalize_constraint_text(constraint_text)
    if not term:
        return ()
    pattern = _term_pattern(term)
    evidence: list[str] = []
    for field in candidate_fields:
        normalized_field = normalize_constraint_text(field)
        if pattern.search(normalized_field):
            evidence.append(field)
    return tuple(dict.fromkeys(evidence))


def evaluate_constraints(
    record: AttractionRecord,
    *,
    required_features: list[str],
    excluded_features: list[str],
) -> tuple[ConstraintAssessment, ...]:
    fields = _candidate_fields(record)
    constraints = normalize_constraints(
        required_features=required_features,
        excluded_features=excluded_features,
    )
    assessments: list[ConstraintAssessment] = []
    for constraint in constraints:
        evidence = find_constraint_evidence(constraint.normalized_text, fields)
        if evidence:
            status: AssessmentStatus = (
                "conflict" if constraint.kind == "excluded" else "match"
            )
        else:
            status = "unknown"
        assessments.append(
            ConstraintAssessment(
                source_text=constraint.source_text,
                normalized_text=constraint.normalized_text,
                kind=constraint.kind,
                status=status,
                evidence=evidence,
            )
        )
    return tuple(assessments)


__all__ = [
    "AssessmentStatus",
    "ConstraintAssessment",
    "evaluate_constraints",
    "find_constraint_evidence",
]
