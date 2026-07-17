import re
from typing import Literal


Language = Literal["ko", "en"]


def detect_input_language(text: str, fallback: str = "ko") -> Language:
    """입력 문자가 충분할 때 언어를 판정하고, 모호하면 UI 설정을 사용한다."""

    normalized_fallback: Language = (
        "en" if str(fallback).lower().startswith("en") else "ko"
    )
    hangul_count = len(re.findall(r"[가-힣]", text))
    latin_words = re.findall(r"\b[A-Za-z]{2,}\b", text)

    if hangul_count >= 2:
        return "ko"
    if len(latin_words) >= 2:
        return "en"
    return normalized_fallback


__all__ = ["Language", "detect_input_language"]
