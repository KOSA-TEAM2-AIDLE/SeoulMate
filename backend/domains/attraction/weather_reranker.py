"""검증된 관광 후보 속성과 Weather MCP 사실을 결합한다."""

from __future__ import annotations

from domains.common.models import SearchCandidate


class AttractionWeatherReranker:
    """명시적 실내·실외 근거가 있는 경우에만 소폭 재랭킹한다."""

    WEATHER_TERMS = (
        "날씨", "비", "눈", "더운", "추운", "강풍", "바람",
        "weather", "rain", "snow", "hot", "cold", "wind",
    )
    INDOOR_TERMS = ("실내", "실내 체험", "indoor")
    OUTDOOR_TERMS = ("야외", "노천", "산책로", "outdoor", "open-air")
    ADJUSTMENT = 0.04

    @classmethod
    def should_use_weather(cls, question: str, *, has_visit_date: bool) -> bool:
        normalized = question.casefold()
        return has_visit_date or any(term in normalized for term in cls.WEATHER_TERMS)

    def rerank(
        self,
        candidates: list[SearchCandidate],
        weather: dict,
        question: str,
    ) -> list[SearchCandidate]:
        if not candidates:
            return []
        available = bool(weather.get("available"))
        condition = str(weather.get("condition") or "").casefold()
        adverse = condition in {"rain", "snow"}
        reranked = [
            self._apply(candidate, weather, available=available, adverse=adverse)
            for candidate in candidates
        ]
        reranked.sort(key=lambda item: item.final_score, reverse=True)
        return reranked

    def _apply(
        self,
        candidate: SearchCandidate,
        weather: dict,
        *,
        available: bool,
        adverse: bool,
    ) -> SearchCandidate:
        signals = dict(candidate.signals)
        signals.update({
            "weather_available": available,
            "weather_condition": weather.get("condition") if available else None,
            "weather_temperature_c": weather.get("temperature_c") if available else None,
            "weather_source": weather.get("source"),
            "weather_error": weather.get("error"),
            "weather_adjustment": 0.0,
            "weather_score": 0.5 if available else None,
            "weather_reasons": [],
        })
        if not available:
            return candidate.model_copy(update={"signals": signals})

        text = " ".join(
            str(candidate.attributes.get(key) or "")
            for key in ("summary", "description", "tags", "kind")
        ).casefold()
        indoor = any(term in text for term in self.INDOOR_TERMS)
        outdoor = any(term in text for term in self.OUTDOOR_TERMS)
        adjustment = 0.0
        reasons: list[str] = []
        if adverse and indoor and not outdoor:
            adjustment = self.ADJUSTMENT
            reasons.append("비·눈 예보와 명시적 실내 시설 근거가 있음")
        elif adverse and outdoor and not indoor:
            adjustment = -self.ADJUSTMENT
            reasons.append("비·눈 예보와 명시적 야외 활동 근거가 있음")
        signals.update({
            "weather_adjustment": adjustment,
            "weather_score": (
                0.75 if adjustment > 0
                else 0.25 if adjustment < 0
                else 0.5
            ),
            "weather_reasons": reasons,
            "weather_indoor_evidence": indoor,
            "weather_outdoor_evidence": outdoor,
        })
        return candidate.model_copy(update={
            "final_score": candidate.final_score + adjustment,
            "signals": signals,
        })


__all__ = ["AttractionWeatherReranker"]
