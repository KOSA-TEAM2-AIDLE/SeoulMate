"""SearchCandidate를 DSPy에 노출하고 관광 도메인 답변 근거로 변환한다."""

from __future__ import annotations

from datetime import date
from typing import Any

from domains.attraction.answer_models import (
    AttractionAnswerInput,
    AttractionConstraintEvidence,
    AttractionContextEvidence,
    AttractionEvidenceCandidate,
)
from domains.attraction.value_normalization import (
    is_nullish,
    optional_text,
    required_text,
)
from domains.common.models import SearchCandidate


MAX_ANSWER_CANDIDATES = 10
MAX_REVIEW_EVIDENCE = 5


def build_attraction_answer_input(
    *,
    question: str,
    language: str,
    location: str | None,
    themes: list[str],
    candidates: list[SearchCandidate],
    today: date | None = None,
) -> AttractionAnswerInput:
    """재랭킹 순서를 유지하며 최대 10개의 검증 근거만 구성한다."""

    as_of = today or date.today()
    evidence_candidates = [
        _to_evidence(candidate, rank=rank, as_of=as_of)
        for rank, candidate in enumerate(
            candidates[:MAX_ANSWER_CANDIDATES],
            start=1,
        )
    ]
    return AttractionAnswerInput(
        question=required_text(question, field="question"),
        language=required_text(language, field="language"),
        location=optional_text(location),
        themes=[
            normalized
            for theme in themes
            if (normalized := optional_text(theme)) is not None
        ],
        candidates=evidence_candidates,
    )


def _to_evidence(
    candidate: SearchCandidate,
    *,
    rank: int,
    as_of: date,
) -> AttractionEvidenceCandidate:
    if candidate.domain != "attraction":
        raise ValueError(f"관광 후보만 변환할 수 있습니다: {candidate.domain}")

    attributes = candidate.attributes
    kind = optional_text(attributes.get("kind")) or ""
    start_date = _optional_date(attributes.get("start_date"), field="start_date")
    end_date = _optional_date(attributes.get("end_date"), field="end_date")
    if kind == "event" and end_date is not None and end_date < as_of:
        raise ValueError(
            f"종료된 행사는 DSPy 후보로 전달할 수 없습니다: {candidate.place_id}"
        )

    return AttractionEvidenceCandidate(
        place_id=required_text(candidate.place_id, field="place_id"),
        rank=rank,
        name=required_text(candidate.name, field="name"),
        category=required_text(candidate.category, field="category"),
        distance_m=_distance_m(attributes.get("distance_km")),
        description=(
            optional_text(attributes.get("description"))
            or optional_text(attributes.get("description_text"))
        ),
        reviews=[
            normalized
            for review in candidate.evidence
            if (normalized := optional_text(review)) is not None
        ][:MAX_REVIEW_EVIDENCE],
        event_start_date=start_date if kind == "event" else None,
        event_end_date=end_date if kind == "event" else None,
        congestion=_congestion_evidence(candidate.signals),
        weather=_weather_evidence(candidate.signals),
        constraints=_constraint_evidence(candidate.signals),
    )


def _optional_date(value: Any, *, field: str) -> date | None:
    if is_nullish(value):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"올바르지 않은 {field} 형식입니다: {value}") from error


def _distance_m(value: Any) -> float | None:
    if is_nullish(value):
        return None
    try:
        distance_km = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"올바르지 않은 distance_km입니다: {value}") from error
    if distance_km < 0:
        raise ValueError("distance_km는 음수일 수 없습니다.")
    return round(distance_km * 1000, 1)


def _congestion_evidence(signals: dict[str, Any]) -> AttractionContextEvidence:
    if signals.get("congestion_available") is not True:
        return AttractionContextEvidence()
    value = optional_text(signals.get("congestion_level"))
    basis = optional_text(signals.get("congestion_basis"))
    observed_at = optional_text(signals.get("congestion_observed_at"))
    if value is None and basis is None and observed_at is None:
        return AttractionContextEvidence()
    return AttractionContextEvidence(
        status="available",
        value=value,
        basis=basis,
        observed_at=observed_at,
    )


def _constraint_evidence(
    signals: dict[str, Any],
) -> list[AttractionConstraintEvidence]:
    raw_items = signals.get("constraint_assessments")
    if not isinstance(raw_items, list):
        return []
    constraints: list[AttractionConstraintEvidence] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        try:
            constraints.append(AttractionConstraintEvidence.model_validate(raw))
        except ValueError:
            continue
    return constraints


def _weather_evidence(signals: dict[str, Any]) -> AttractionContextEvidence:
    if signals.get("weather_available") is not True:
        return AttractionContextEvidence()
    parts = []
    for label, key in (
        ("condition", "weather_condition"),
        ("temperature_c", "weather_temperature_c"),
    ):
        value = optional_text(signals.get(key))
        if value is not None:
            parts.append(f"{label}={value}")
    reasons = signals.get("weather_reasons")
    if isinstance(reasons, list):
        parts.extend(str(reason) for reason in reasons if optional_text(reason))
    value = "; ".join(parts) or None
    basis = optional_text(signals.get("weather_source"))
    if value is None and basis is None:
        return AttractionContextEvidence()
    return AttractionContextEvidence(
        status="available",
        value=value,
        basis=basis,
    )


__all__ = ["build_attraction_answer_input"]
