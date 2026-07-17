"""관광 도메인의 구조화된 요구·제외 조건을 정규화한다.

이 모듈은 사격·물놀이 같은 도메인 개념을 해석하지 않는다. 상위 질의
파서가 나눈 required/excluded 극성을 그대로 보존하고 문자열 비교를 위한
표면 형태만 정리한다.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Literal


ConstraintKind = Literal["required", "excluded"]


@dataclass(frozen=True)
class NormalizedConstraint:
    source_text: str
    normalized_text: str
    kind: ConstraintKind


def normalize_constraint_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or "")).casefold()
    normalized = re.sub(r"[_/|]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip(" \t\r\n,.;:!?\"'`()[]{}")


def normalize_constraints(
    *,
    required_features: list[str],
    excluded_features: list[str],
) -> tuple[NormalizedConstraint, ...]:
    constraints: list[NormalizedConstraint] = []
    seen: set[tuple[ConstraintKind, str]] = set()
    for kind, features in (
        ("required", required_features),
        ("excluded", excluded_features),
    ):
        for feature in features:
            source = str(feature or "").strip()
            normalized = normalize_constraint_text(source)
            key = (kind, normalized)
            if not normalized or key in seen:
                continue
            seen.add(key)
            constraints.append(NormalizedConstraint(source, normalized, kind))
    return tuple(constraints)


__all__ = [
    "ConstraintKind",
    "NormalizedConstraint",
    "normalize_constraint_text",
    "normalize_constraints",
]
