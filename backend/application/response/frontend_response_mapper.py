"""내부 Place/DayPlan을 프론트 최종 JSON으로 변환한다."""

from __future__ import annotations

import math

from schemas.chat import DayPlan, TimeSlot
from schemas.common import Place
from schemas.frontend_response import FrontendPlace, FrontendResponse, FrontendResponseType


CATEGORY_LABELS = {
    "restaurant": "맛집",
    "cafe": "카페",
    "accommodation": "숙소",
    "attraction": "관광지",
    "event": "문화시설",
    "etc": "기타",
}


def _rating_text(value: float | None) -> str | None:
    if value is None:
        return None
    rating = float(value)
    if not math.isfinite(rating) or not 0 <= rating <= 5:
        return None
    return f"{rating:.1f}"


def _review_text(value: int | None) -> str | None:
    if value is None or int(value) < 0:
        return None
    return f"{int(value):,}"


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _latitude(value: float | None) -> float | None:
    if value is None:
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) and -90 <= parsed <= 90 else None


def _longitude(value: float | None) -> float | None:
    if value is None:
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) and -180 <= parsed <= 180 else None


def _slot_time(slot: TimeSlot) -> str | None:
    if not slot.time:
        return None
    if slot.end_time:
        if slot.end_date and slot.date and slot.end_date != slot.date:
            return f"{slot.time} - {slot.end_date} {slot.end_time}"
        return f"{slot.time} - {slot.end_time}"
    return slot.time


def frontend_place(
    place: Place,
    *,
    visit_time: str | None = None,
    slot_id: str | None = None,
    alternatives: list[Place] | None = None,
) -> FrontendPlace:
    """GPT가 상세 값을 만들지 못하도록 Place에 이미 존재하는 값만 복사한다."""

    return FrontendPlace(
        id=place.restaurant_id or place.source_id,
        slotId=slot_id,
        name=place.name,
        category=CATEGORY_LABELS.get(place.source_type, place.category or "기타"),
        subCategory=_optional_text(place.category),
        address=_optional_text(place.address),
        lat=_latitude(place.lat),
        lng=_longitude(place.lng),
        rating=_rating_text(place.rating),
        reviews=_review_text(place.review_count),
        time=visit_time,
        image=_optional_text(place.image),
        selectionReason=_optional_text(place.selection_reason or place.reason),
        link=_optional_text(place.link),
        price=_optional_text(place.price),
        live_rating=_optional_text(place.live_rating),
        features=_optional_text(place.features),
        alternatives=[frontend_place(item) for item in (alternatives or [])],
    )


def recommendation_frontend_response(places: list[Place]) -> FrontendResponse:
    """단일 추천은 검증된 최종 순위에서 최대 3개만 노출한다."""

    ranked = sorted(
        places,
        key=lambda place: (
            place.rank is None,
            place.rank if place.rank is not None else 999,
        ),
    )
    return FrontendResponse(
        responseType="recommendation",
        day=None,
        allDay=None,
        travelPath=None,
        recommendList=[frontend_place(place) for place in ranked[:3]],
    )


def route_frontend_response(
    days: list[DayPlan],
    *,
    active_day: int = 1,
    accommodation: Place | None = None,
    accommodation_alternatives: list[Place] | None = None,
) -> FrontendResponse:
    """날짜별 내부 슬롯을 연속된 travelPath 키로 직렬화한다."""

    ordered_days = sorted(days, key=lambda item: item.day)
    travel_path: dict[str, list[FrontendPlace]] = {}
    for expected_day, day_plan in enumerate(ordered_days, start=1):
        if day_plan.day != expected_day:
            raise ValueError("루트 day는 1부터 연속이어야 합니다.")
        travel_path[str(day_plan.day)] = [
            frontend_place(
                slot.place,
                visit_time=_slot_time(slot),
                slot_id=slot.slot_id,
                alternatives=slot.alternatives,
            )
            for slot in sorted(day_plan.slots, key=lambda item: (item.time, item.slot_id or ""))
        ]
    if not travel_path:
        raise ValueError("route 응답에는 하나 이상의 day가 필요합니다.")
    return FrontendResponse(
        responseType="route",
        day=active_day,
        allDay=len(travel_path),
        travelPath=travel_path,
        accommodation=(
            frontend_place(
                accommodation,
                alternatives=accommodation_alternatives,
            )
            if accommodation is not None
            else None
        ),
        recommendList=None,
    )


def empty_frontend_response(response_type: FrontendResponseType) -> FrontendResponse:
    if response_type in {"route", "recommendation"}:
        raise ValueError("route/recommendation은 전용 변환 함수를 사용해야 합니다.")
    return FrontendResponse(
        responseType=response_type,
        day=None,
        allDay=None,
        travelPath=None,
        recommendList=None,
    )


__all__ = [
    "empty_frontend_response",
    "frontend_place",
    "recommendation_frontend_response",
    "route_frontend_response",
]
