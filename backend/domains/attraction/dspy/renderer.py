"""Convert validated DSPy output into the existing chat selection contract."""

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
            selection_reason=_sidebar_reason(
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
            _natural_recommendation(index, item, answer.language)
            for index, item in enumerate(answer.recommendations, start=1)
        )
        text = "\n\n".join(sections)
    return CandidateSelectionResult(answer=text, selections=selections)


def _sidebar_reason(
    query_reason: str,
    recommendation: AttractionStructuredRecommendation | None,
    language: str,
) -> str:
    if recommendation is None:
        return query_reason
    separator = " · "
    return separator.join((
        _query_reason(query_reason, language),
        _context_reason("congestion", recommendation.congestion, language),
        _context_reason("weather", recommendation.weather, language),
    ))


def _query_reason(reason: str, language: str) -> str:
    return (
        f"Query fit: {reason}"
        if language.casefold().startswith("en")
        else f"질의 적합성: {reason}"
    )


def _context_reason(kind: str, context: AttractionAnswerContext, language: str) -> str:
    korean = not language.casefold().startswith("en")
    label = (
        {"congestion": "Congestion", "weather": "Weather"}[kind]
        if not korean else {"congestion": "혼잡도", "weather": "날씨"}[kind]
    )
    if context.status == "unavailable":
        return (
            f"{label}: current observation unavailable"
            if not korean else f"{label}: 현재 관측 정보 없음"
        )
    details = [context.value]
    if context.basis:
        details.append(context.basis)
    if context.observed_at:
        details.append(context.observed_at)
    return f"{label}: {' / '.join(details)}"


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
    language: str,
) -> str:
    if language.casefold().startswith("en"):
        return _natural_recommendation_en(index, item)
    parts = [f"{index}. {item.name}", _natural_place_reason(item)]
    if item.description_evidence:
        parts.append(f"또한, {item.description_evidence[0]}")
    if item.congestion.status == "available":
        provenance = _provenance(item.congestion)
        parts.append(
            f"현재 혼잡도는 {item.congestion.value} 수준으로 확인되어, 비교적 여유롭게 이용하기 좋습니다{provenance}."
        )
    else:
        parts.append("현재 혼잡도 정보는 확인되지 않아 방문 전 다시 확인해 주세요.")
    if item.weather.status == "available":
        parts.append(f"현재 날씨 정보는 {item.weather.value}입니다{_provenance(item.weather)}.")
    else:
        parts.append("현재 날씨 정보는 확인되지 않아 방문 전 다시 확인해 주세요.")
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
) -> str:
    parts = [f"{index}. {item.name}", item.recommendation_reason]
    if item.description_evidence:
        parts.append(item.description_evidence[0])
    if item.congestion.status == "available":
        parts.append(f"Current congestion is {item.congestion.value}, so it should be relatively comfortable to visit{_provenance(item.congestion, english=True)}.")
    else:
        parts.append("Current congestion information is unavailable; please check again before visiting.")
    if item.weather.status == "available":
        parts.append(f"Current weather information: {item.weather.value}{_provenance(item.weather, english=True)}.")
    else:
        parts.append("Current weather information is unavailable; please check again before visiting.")
    if item.visitor_note:
        parts.append(item.visitor_note)
    return f"{parts[0]}\n   " + " ".join(parts[1:])


def _provenance(context: AttractionAnswerContext, *, english: bool = False) -> str:
    values = [value for value in (context.basis, context.observed_at) if value]
    if not values:
        return ""
    label = " (source: " if english else " (기준: "
    return label + " / ".join(values) + ")"


__all__ = ["render_selection_result"]
