"""RAG 후보의 관련성을 보존하면서 날씨 적합도로 소폭 재랭킹한다."""

from __future__ import annotations

import re

from core.config import WEATHER_RERANK_WEIGHT


STRONG_OUTDOOR_WORDS = {
    "루프탑", "테라스", "야외석", "야외 좌석", "야외 테이블",
    "rooftop", "terrace", "outdoor seating", "outdoor seats", "outdoor tables",
}
OUTDOOR_NEGATIONS = {
    "없", "운영하지 않", "폐쇄", "이용 불가", "실내만",
    "no outdoor", "no terrace", "not available", "closed", "indoor only",
}
WEATHER_INTENT_WORDS = {
    "날씨", "비", "눈", "더운", "추운", "강풍", "바람",
    "오늘 저녁", "오늘 밤", "내일", "모레",
    "weather", "rain", "snow", "hot", "cold", "wind", "tonight", "tomorrow",
}
STRONG_WIND_MPS = 7.0
RAG_MCP_MODE = "rag_mcp"


def prepare_rag_only_candidates(candidates: list[dict]) -> list[dict]:
    """RAG_ONLY 후보에서 날씨 파생값을 제거하고 원래 검색 순서와 점수를 보존한다."""
    for candidate in candidates:
        candidate["rag_score"] = float(candidate["score"])
        candidate["weather_score"] = None
        candidate["weather_reasons"] = []
        candidate.pop("outdoor_confidence", None)
    return candidates


def get_outdoor_confidence(candidate: dict) -> str:
    text = " ".join(
        str(candidate.get(field) or "")
        for field in ("description", "description_kakao")
    ).lower()
    sentences = [part.strip() for part in re.split(r"[.!?。！？\n]+", text) if part.strip()]
    for sentence in sentences:
        if not any(keyword in sentence for keyword in STRONG_OUTDOOR_WORDS):
            continue
        if any(negation in sentence for negation in OUTDOOR_NEGATIONS):
            continue
        return "high"
    return "unknown"


def _menu_reason(prefix: str, matches: list[str]) -> str:
    shown = ", ".join(matches[:3])
    return f"{prefix} ({shown})" if shown else prefix


def calculate_weather_fit(candidate: dict, weather: dict) -> tuple[float, list[str]]:
    score = 0.5
    reasons: list[str] = []
    condition = weather.get("condition")
    temperature = weather.get("temperature_c")
    wind_speed = weather.get("wind_speed_mps")
    features = candidate.get("weather_features") or {}
    outdoor_confidence = candidate.get("outdoor_confidence") or get_outdoor_confidence(candidate)

    if condition in {"rain", "snow"}:
        distance = candidate.get("distance_km")
        if distance is not None and distance <= 0.5:
            score += 0.12
            reasons.append("비나 눈이 올 때 이동 부담이 매우 적은 500m 이내 거리")
        elif distance is not None and distance <= 1.0:
            score += 0.07
            reasons.append("비나 눈이 올 때 이동 부담이 적은 1km 이내 거리")
        elif distance is not None and distance >= 1.5:
            score -= 0.05
            reasons.append("비나 눈이 올 때 직선거리 기준 이동 거리가 다소 멂")
        if candidate.get("has_parking") is True:
            score += 0.10
            reasons.append("비나 눈이 올 때 편리한 주차 가능")
        if wind_speed is not None and wind_speed >= STRONG_WIND_MPS:
            if distance is not None and distance >= 1.0:
                score -= 0.07
                reasons.append("비나 눈과 강풍이 겹쳐 거리가 먼 후보는 이동에 불리함")
            if outdoor_confidence == "high":
                score -= 0.08
                reasons.append("강풍이 불 때 야외 좌석 이용에 불리함")
        if outdoor_confidence == "high":
            score -= 0.15
            reasons.append("비나 눈이 올 때 루프탑·테라스 이용에 불리함")

    if temperature is not None and temperature >= 28 and features.get("has_cool_menu"):
        score += 0.15
        reasons.append(_menu_reason(
            "더운 날 어울리는 시원한 메뉴가 있음",
            features.get("cool_menu_matches", []),
        ))
    if temperature is not None and temperature < 5 and features.get("has_warm_menu"):
        score += 0.15
        reasons.append(_menu_reason(
            "추운 날 어울리는 따뜻한 메뉴가 있음",
            features.get("warm_menu_matches", []),
        ))

    return min(max(score, 0.0), 1.0), reasons


def rerank_with_weather(
    candidates: list[dict],
    weather: dict,
    query: str,
    *,
    source_mode: str = RAG_MCP_MODE,
) -> list[dict]:
    # 호출부가 실수로 RAG_ONLY 후보를 넘겨도 날씨가 점수나 순서를 바꾸지 못하게 한다.
    if str(source_mode).strip().lower() != RAG_MCP_MODE:
        return prepare_rag_only_candidates(candidates)
    if not candidates:
        return []
    if not weather.get("available"):
        for candidate in candidates:
            candidate["rag_score"] = candidate["score"]
            candidate["weather_score"] = None
            candidate["weather_reasons"] = []
            candidate["outdoor_confidence"] = get_outdoor_confidence(candidate)
        return candidates

    scores = [float(candidate["score"]) for candidate in candidates]
    high = max(scores)
    weather_intent = any(word in query.lower() for word in WEATHER_INTENT_WORDS)
    weather_weight = min(0.2, WEATHER_RERANK_WEIGHT * (2 if weather_intent else 1))

    for candidate in candidates:
        raw_score = float(candidate["score"])
        # 최고점 대비 비율을 써서 점수가 근소한 후보끼리만 날씨가 순서를 바꾸게 한다.
        rag_normalized = 1.0 if high <= 0 else max(raw_score / high, 0.0)
        candidate["outdoor_confidence"] = get_outdoor_confidence(candidate)
        weather_score, reasons = calculate_weather_fit(candidate, weather)
        candidate["rag_score"] = raw_score
        candidate["weather_score"] = weather_score
        candidate["weather_reasons"] = reasons
        candidate["score"] = rag_normalized * (1 - weather_weight) + weather_score * weather_weight

    candidates.sort(
        key=lambda item: (-item["score"], -item.get("rag_score", 0), item["restaurant_id"])
    )
    return candidates
