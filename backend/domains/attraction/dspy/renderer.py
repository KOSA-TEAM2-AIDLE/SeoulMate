"""Convert validated DSPy output into the existing chat selection contract."""

from datetime import datetime

from application.recommendation.selection_models import (
    CandidateSelection,
    CandidateSelectionResult,
)
from domains.attraction.dspy.contracts import (
    AttractionAnswerContext,
    AttractionSelectionPrediction,
    AttractionStructuredRecommendation,
    AttractionStructuredAnswer,
)


def render_selection_result(
    selection: AttractionSelectionPrediction,
    answer: AttractionStructuredAnswer,
    *,
    question: str = "",
) -> CandidateSelectionResult:
    recommendations = {item.place_id: item for item in answer.recommendations}
    selections = [
        CandidateSelection(
            place_id=place_id,
            selection_reason=render_place_recommendation_reason(
                selection.selection_reasons[place_id],
                recommendations.get(place_id),
                answer.language,
            ),
        )
        for place_id in selection.selected_place_ids
    ]
    if not answer.recommendations:
        text = answer.no_result_reason or "검증된 관광지 후보가 없습니다."
    else:
        sections = [_intro(question, answer.language)]
        sections.extend(
            _natural_recommendation(
                index,
                item,
                selection.selection_reasons[item.place_id],
                answer.language,
            )
            for index, item in enumerate(answer.recommendations, start=1)
        )
        text = "\n\n".join(sections)
    return CandidateSelectionResult(answer=text, selections=selections)


def render_place_recommendation_reason(
    query_reason: str,
    recommendation: AttractionStructuredRecommendation | None,
    language: str,
) -> str:
    if recommendation is None:
        return query_reason
    if language.casefold().startswith("en"):
        return " ".join((
            query_reason.strip(),
            _english_context_sentence("congestion", recommendation.congestion),
            _english_context_sentence("weather", recommendation.weather),
        ))
    return " ".join((
        query_reason.strip(),
        _korean_context_sentence("congestion", recommendation.congestion),
        _korean_context_sentence("weather", recommendation.weather),
    ))


def _korean_context_sentence(kind: str, context: AttractionAnswerContext) -> str:
    label = "혼잡도" if kind == "congestion" else "날씨"
    if context.status == "unavailable":
        return f"{label} 정보는 확인되지 않았습니다."
    if kind == "weather":
        return f"현재 날씨는 {_weather_summary(context.value, english=False)}입니다{_provenance(context)}."
    level = " 수준" if kind == "congestion" else ""
    return f"현재 {label}는 {context.value}{level}입니다{_provenance(context)}."


def _english_context_sentence(kind: str, context: AttractionAnswerContext) -> str:
    label = "congestion" if kind == "congestion" else "weather"
    if context.status == "unavailable":
        return f"{label.capitalize()} information is unavailable."
    if kind == "weather":
        return f"Current weather is {_weather_summary(context.value, english=True)}{_provenance(context, english=True)}."
    value = _english_context_value(kind, context.value)
    return f"Current {label} is {value}{_provenance(context, english=True)}."


def _english_context_value(kind: str, value: str | None) -> str | None:
    if kind != "congestion" or value is None:
        return value
    return {
        "여유": "Low",
        "보통": "Moderate",
        "약간 붐빔": "Slightly busy",
        "붐빔": "Busy",
        "혼잡": "Crowded",
    }.get(value.strip(), value)


def _weather_summary(value: str | None, *, english: bool) -> str:
    fields = {}
    for item in str(value or "").split(";"):
        key, separator, raw = item.partition("=")
        if separator:
            fields[key.strip()] = raw.strip()
    condition = fields.get("condition")
    if condition:
        condition = {
            "clear": "Clear" if english else "맑음",
            "cloudy": "Cloudy" if english else "흐림",
            "partly_cloudy": "Partly cloudy" if english else "구름 조금",
            "rain": "Rain" if english else "비",
            "snow": "Snow" if english else "눈",
        }.get(condition.casefold(), condition)
    temperature = fields.get("temperature_c")
    parts = [part for part in (condition, f"{temperature}°C" if temperature else None) if part]
    return ", ".join(parts) or (value or "정보 없음")


def _intro(question: str, language: str) -> str:
    if language.casefold().startswith("en"):
        return (
            f"Based on your request, “{question},” here are places I recommend."
            if question else "Here are places I recommend based on your request."
        )
    return (
        f"“{question}” 조건을 기준으로 다음 장소를 추천드릴게요."
        if question else "요청하신 조건을 기준으로 다음 장소를 추천드릴게요."
    )


def _natural_recommendation(
    index: int,
    item: AttractionStructuredRecommendation,
    query_reason: str,
    language: str,
) -> str:
    if language.casefold().startswith("en"):
        return _natural_recommendation_en(index, item, query_reason)
    parts = [f"{index}. {item.name}", render_place_recommendation_reason(query_reason, item, language)]
    if item.description_evidence:
        parts.append(f"또한, {item.description_evidence[0]}")
    if item.visitor_note:
        parts.append(item.visitor_note)
    return f"{parts[0]}\n   " + " ".join(parts[1:])


def _natural_place_reason(item: AttractionStructuredRecommendation) -> str:
    """Avoid adding a second subject to a complete DSPy recommendation sentence."""
    reason = item.recommendation_reason.strip()
    aliases = (item.name, item.name.split(" (", maxsplit=1)[0])
    if any(alias and reason.startswith(alias) for alias in aliases):
        return reason
    words = [word.rstrip(",.") for word in reason.split()[:8]]
    if any(word.endswith(("은", "는", "이", "가")) for word in words):
        return reason
    return f"이곳은 {reason}"


def _natural_recommendation_en(
    index: int,
    item: AttractionStructuredRecommendation,
    query_reason: str,
) -> str:
    parts = [f"{index}. {item.name}", render_place_recommendation_reason(query_reason, item, "en")]
    if item.description_evidence:
        parts.append(item.description_evidence[0])
    if item.visitor_note:
        parts.append(item.visitor_note)
    return f"{parts[0]}\n   " + " ".join(parts[1:])


def _provenance(context: AttractionAnswerContext, *, english: bool = False) -> str:
    observed_at = (
        _format_observed_at_english(context.observed_at)
        if english
        else _format_observed_at(context.observed_at)
    )
    values = [value for value in (context.basis, observed_at) if value]
    if not values:
        return ""
    label = " (source: " if english else " (기준: "
    return label + " / ".join(values) + ")"


def _format_observed_at(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _format_observed_at_english(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    hour = parsed.strftime("%I").lstrip("0") or "0"
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}, {hour}:{parsed.strftime('%M %p')}"


__all__ = ["render_selection_result"]
