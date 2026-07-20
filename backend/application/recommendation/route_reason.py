"""루트 슬롯의 추천 이유를 도메인과 무관하게 같은 문장 골격으로 만든다.

기존에는 식당·카페·관광지·숙소가 각자 다른 파일에서 이유 문장을 만들어
리뷰 원문, DB 설명문, 제네릭 문장이 한 화면에 섞여 나왔다. 여기서는
검색기가 이미 검증한 값만 사용해 네 도메인이 같은 문장 구조를 갖게 한다.

문장 골격(ko): "{평점 근거}의 {카테고리}{로}, {도메인 근거}{동선 근거}입니다."
값이 없는 조각은 문장에서 자연스럽게 빠지고, 남는 조각이 없으면
공통 폴백 문구를 쓴다. 추측한 사실은 절대 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass


DOMAIN_CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "restaurant": {"ko": "식당", "en": "restaurant"},
    "cafe": {"ko": "카페", "en": "cafe"},
    "attraction": {"ko": "관광지", "en": "attraction"},
    "accommodation": {"ko": "숙소", "en": "place to stay"},
}
DEFAULT_CATEGORY_LABEL = {"ko": "추천 장소", "en": "recommended place"}


@dataclass(frozen=True)
class RouteReasonFacts:
    """루트 슬롯 하나의 이유 문장을 만들기 위한 검증된 사실 모음."""

    domain: str
    category: str | None = None
    rating: float | None = None
    review_count: int | None = None
    # 식당: 해당 방문 시각에 영업이 확인된 경우에만 True. 알 수 없으면 None.
    open_at_visit_time: bool | None = None
    visit_time: str | None = None
    # 관광지: 날씨 재랭커가 명시적 실내·야외 근거를 찾은 경우에만 채운다.
    # 날씨 문구는 비·눈처럼 일정에 실제로 영향을 주는 예보에서만 쓴다.
    weather_condition: str | None = None
    weather_indoor_evidence: bool = False
    weather_outdoor_evidence: bool = False
    # 공통 동선 근거. 첫 방문지는 직전 일정이 없으므로 is_first_stop을 쓴다.
    distance_from_previous_km: float | None = None
    is_first_stop: bool = False
    # 숙소는 특정 슬롯이 아니라 일정 전체와의 거리로 설명한다.
    distance_from_area_km: float | None = None


def _is_english(language: str | None) -> bool:
    return str(language or "").lower().startswith("en")


def _category_label(facts: RouteReasonFacts, *, english: bool) -> str:
    key = "en" if english else "ko"
    category = str(facts.category or "").strip()
    if category:
        return category
    domain_label = DOMAIN_CATEGORY_LABELS.get(facts.domain)
    if domain_label:
        return domain_label[key]
    return DEFAULT_CATEGORY_LABEL[key]


def _format_rating(rating: float) -> str:
    return f"{rating:.1f}".rstrip("0").rstrip(".")


def _format_distance(distance_km: float) -> str:
    if distance_km < 1:
        return f"{round(distance_km * 1000 / 10) * 10}m"
    return f"{distance_km:.1f}km"


def _josa_ro(word: str) -> str:
    """받침에 따라 '로'와 '으로'를 고른다. 한글이 아니면 '로'를 쓴다."""

    if not word:
        return "로"
    last = word[-1]
    if not "가" <= last <= "힣":
        return "로"
    final_consonant = (ord(last) - 0xAC00) % 28
    # 받침이 없거나 ㄹ 받침이면 '로'가 자연스럽다.
    return "로" if final_consonant in (0, 8) else "으로"


def _korean_head(facts: RouteReasonFacts, category: str) -> str:
    if facts.rating is not None and facts.review_count:
        return f"평점 {_format_rating(facts.rating)}(리뷰 {facts.review_count}개)의 {category}"
    if facts.rating is not None:
        return f"평점 {_format_rating(facts.rating)}의 {category}"
    if facts.review_count:
        return f"리뷰 {facts.review_count}개의 {category}"
    return category


def _english_head(facts: RouteReasonFacts, category: str) -> str:
    article = "An" if category[:1].lower() in "aeiou" else "A"
    if facts.rating is not None and facts.review_count:
        return (
            f"{article} {category} rated {_format_rating(facts.rating)}"
            f" ({facts.review_count} reviews)"
        )
    if facts.rating is not None:
        return f"{article} {category} rated {_format_rating(facts.rating)}"
    if facts.review_count:
        return f"{article} {category} with {facts.review_count} reviews"
    return f"{article} {category}"


ADVERSE_WEATHER_CONDITIONS = frozenset({"rain", "snow"})


def _adverse_weather(facts: RouteReasonFacts) -> bool:
    return str(facts.weather_condition or "").casefold() in ADVERSE_WEATHER_CONDITIONS


def _korean_lead_clauses(facts: RouteReasonFacts) -> list[str]:
    clauses: list[str] = []
    if facts.open_at_visit_time and facts.visit_time:
        clauses.append(f"{facts.visit_time} 방문 시간에 영업하며")
    if _adverse_weather(facts) and facts.weather_indoor_evidence:
        clauses.append("비·눈 예보에 맞는 실내 장소이며")
    elif _adverse_weather(facts) and facts.weather_outdoor_evidence:
        clauses.append("예보를 함께 확인한 야외 장소이며")
    return clauses


def _english_lead_clauses(facts: RouteReasonFacts) -> list[str]:
    clauses: list[str] = []
    if facts.open_at_visit_time and facts.visit_time:
        clauses.append(f"open at {facts.visit_time}")
    if _adverse_weather(facts) and facts.weather_indoor_evidence:
        clauses.append("an indoor option for the forecast rain or snow")
    elif _adverse_weather(facts) and facts.weather_outdoor_evidence:
        clauses.append("an outdoor spot checked against the forecast")
    return clauses


def _korean_final_clause(facts: RouteReasonFacts) -> str:
    if facts.distance_from_area_km is not None:
        return f"일정 권역에서 {_format_distance(facts.distance_from_area_km)} 거리"
    if facts.distance_from_previous_km is not None:
        return f"직전 일정에서 {_format_distance(facts.distance_from_previous_km)} 거리"
    if facts.is_first_stop:
        return "그날 일정의 첫 방문지"
    return "요청 조건과 이동 동선을 함께 고려한 선택"


def _english_final_clause(facts: RouteReasonFacts) -> str:
    if facts.distance_from_area_km is not None:
        return f"{_format_distance(facts.distance_from_area_km)} from the itinerary area"
    if facts.distance_from_previous_km is not None:
        return f"{_format_distance(facts.distance_from_previous_km)} from the previous stop"
    if facts.is_first_stop:
        return "the first stop of the day"
    return "chosen for the requested conditions and the travel route"


def build_route_reason(facts: RouteReasonFacts, language: str | None = "ko") -> str:
    """네 도메인이 공유하는 한 문장짜리 추천 이유를 만든다."""

    english = _is_english(language)
    category = _category_label(facts, english=english)
    if english:
        clauses = [*_english_lead_clauses(facts), _english_final_clause(facts)]
        body = clauses[0] if len(clauses) == 1 else (
            f"{', '.join(clauses[:-1])} and {clauses[-1]}"
        )
        return f"{_english_head(facts, category)}, {body}."
    head = _korean_head(facts, category)
    clauses = [*_korean_lead_clauses(facts), _korean_final_clause(facts)]
    return f"{head}{_josa_ro(head)}, {' '.join(clauses)}입니다."


__all__ = ["RouteReasonFacts", "build_route_reason"]
