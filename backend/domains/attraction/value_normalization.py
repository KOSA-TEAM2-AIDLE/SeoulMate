"""DSPy 경계에서 문자열형 결측치를 일관되게 판별한다."""

from __future__ import annotations

import math
from typing import Any


NULLISH_TEXT_VALUES = frozenset({
    "",
    "null",
    "none",
    "nan",
    "n/a",
    "na",
    "undefined",
})


def is_nullish(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and value.strip().casefold() in (
        NULLISH_TEXT_VALUES
    )


def optional_text(value: Any) -> str | None:
    if is_nullish(value):
        return None
    text = str(value).strip()
    return text or None


def required_text(value: Any, *, field: str) -> str:
    text = optional_text(value)
    if text is None:
        raise ValueError(f"{field}는 필수 문자열이어야 합니다.")
    return text


__all__ = [
    "NULLISH_TEXT_VALUES",
    "is_nullish",
    "optional_text",
    "required_text",
]
