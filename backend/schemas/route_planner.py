"""여행 요청 계약과 백엔드 Route Planner 입출력 모델."""

from __future__ import annotations

from datetime import date, time, timedelta
import re
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)


MAX_ROUTE_DAYS = 7
MAX_SLOTS_PER_DAY = 5
MAX_ROUTE_SLOTS = MAX_ROUTE_DAYS * MAX_SLOTS_PER_DAY
ROUTE_CANDIDATES_PER_SLOT = 5
ROUTE_FALLBACKS_PER_SLOT = 2

RouteDomain = Literal["cafe", "restaurant", "accommodation", "attraction", "etc"]
RoutePace = Literal["relaxed", "normal", "packed"]
HHMMTime = Annotated[
    time,
    PlainSerializer(
        lambda value: value.strftime("%H:%M"),
        return_type=str,
        when_used="json",
    ),
]


class TripPeriod(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start_date: date
    end_date: date
    nights: int = Field(ge=0, le=MAX_ROUTE_DAYS - 1)
    days: int = Field(ge=1, le=MAX_ROUTE_DAYS)

    @model_validator(mode="after")
    def validate_period(self):
        actual_days = (self.end_date - self.start_date).days + 1
        if actual_days != self.days or self.nights != self.days - 1:
            raise ValueError("날짜 범위, nights, days가 서로 일치해야 합니다.")
        return self


# 첫 GPT 계약에서 사용하던 이름을 Route Planner 계약과 동일 모델로 유지한다.
TravelPeriod = TripPeriod


class RouteBudget(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_krw: int | None = Field(default=None, ge=0)
    daily_krw: int | None = Field(default=None, ge=0)
    accommodation_total_krw: int | None = Field(default=None, ge=0)
    meal_per_person_krw: int | None = Field(default=None, ge=0)


class RouteRequest(BaseModel):
    """첫 GPT가 확정한 신규 일정 요청."""

    model_config = ConfigDict(extra="ignore")

    destination: str = Field(min_length=1)
    period: TripPeriod
    adults: int = Field(default=1, ge=1, le=100)
    children: int = Field(default=0, ge=0, le=100)
    arrival_at: HHMMTime | None = None
    arrival_location: str | None = None
    departure_at: HHMMTime | None = None
    departure_location: str | None = None
    accommodation_id: str | None = None
    preferred_accommodation_areas: list[str] = Field(default_factory=list)
    pace: RoutePace = "normal"
    max_places_per_day: int = Field(default=5, ge=1, le=MAX_SLOTS_PER_DAY)
    target_places_per_day: int | None = Field(
        default=None,
        ge=1,
        le=MAX_SLOTS_PER_DAY,
    )
    transportation: list[str] = Field(default_factory=list)
    budget: RouteBudget = Field(default_factory=RouteBudget)
    preferred_areas: list[str] = Field(default_factory=list)
    preferred_themes: list[str] = Field(default_factory=list)
    required_features: list[str] = Field(default_factory=list)
    excluded_features: list[str] = Field(default_factory=list)
    must_visit: list[str] = Field(default_factory=list)
    avoid_places: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_place_target(self):
        if (
            self.target_places_per_day is not None
            and self.target_places_per_day > self.max_places_per_day
        ):
            raise ValueError(
                "target_places_per_day는 max_places_per_day를 초과할 수 없습니다."
            )
        return self


class RouteCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidate_id: str = Field(min_length=1)
    domain: RouteDomain
    place_id: str = Field(min_length=1)
    restaurant_id: str | None = None
    name: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)


class RouteSlotCandidates(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slot_id: str = Field(min_length=1)
    day_number: int = Field(ge=1, le=MAX_ROUTE_DAYS)
    date: date
    start_time: str
    end_date: date | None = None
    end_time: str | None = None
    domain: RouteDomain
    candidates: list[RouteCandidate] = Field(
        min_length=1,
        max_length=ROUTE_CANDIDATES_PER_SLOT,
    )

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, value: str | None):
        if value is None:
            return value
        match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", value.strip())
        if not match:
            raise ValueError("시간은 H:MM, HH:MM 또는 HH:MM:SS 형식이어야 합니다.")
        try:
            parsed = time(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3) or 0),
            )
        except ValueError as exc:
            raise ValueError("유효하지 않은 시간입니다.") from exc
        return parsed.isoformat(timespec="minutes")

    @model_validator(mode="after")
    def validate_candidate_domain(self):
        if any(candidate.domain != self.domain for candidate in self.candidates):
            raise ValueError("슬롯과 후보의 domain이 일치해야 합니다.")
        ids = [candidate.candidate_id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("한 슬롯의 candidate_id는 중복될 수 없습니다.")
        place_keys = [
            (candidate.domain, candidate.place_id) for candidate in self.candidates
        ]
        if len(place_keys) != len(set(place_keys)):
            raise ValueError("한 슬롯에 같은 장소가 중복될 수 없습니다.")
        if self.end_date and self.end_date < self.date:
            raise ValueError("end_date는 슬롯 date보다 빠를 수 없습니다.")
        if self.end_time:
            effective_end_date = self.end_date or self.date
            if effective_end_date == self.date and self.end_time <= self.start_time:
                raise ValueError("같은 날짜의 end_time은 start_time보다 늦어야 합니다.")
        return self


class RoutePlannerInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language: str = "ko"
    original_question: str = Field(min_length=1)
    route_request: RouteRequest
    slots: list[RouteSlotCandidates] = Field(min_length=1, max_length=MAX_ROUTE_SLOTS)
    weather_by_day: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_slot_limits(self):
        slot_ids = [slot.slot_id for slot in self.slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("slot_id는 중복될 수 없습니다.")
        counts: dict[int, int] = {}
        for slot in self.slots:
            if slot.day_number > self.route_request.period.days:
                raise ValueError("슬롯의 day_number가 여행 기간을 벗어났습니다.")
            expected_date = self.route_request.period.start_date + timedelta(
                days=slot.day_number - 1
            )
            if slot.date != expected_date:
                raise ValueError("슬롯의 date와 day_number가 여행 기간과 일치하지 않습니다.")
            if slot.end_date and slot.end_date > self.route_request.period.end_date:
                raise ValueError("슬롯의 end_date가 여행 기간을 벗어났습니다.")
            counts[slot.day_number] = counts.get(slot.day_number, 0) + 1
            if counts[slot.day_number] > self.route_request.max_places_per_day:
                raise ValueError("하루 슬롯이 max_places_per_day를 초과했습니다.")
        return self


class RouteSlotSelection(BaseModel):
    """Route Planner GPT가 반환하는 최소 선택 단위."""

    model_config = ConfigDict(extra="ignore")

    slot_id: str
    selected_candidate_id: str
    selection_reason: str = ""
    alternatives: list["RouteAlternativeSelection"] = Field(default_factory=list)


class RouteAlternativeSelection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidate_id: str
    selection_reason: str = ""


class RoutePlannerDraft(BaseModel):
    """GPT는 하나의 기본 루트만 반환하며 fallback은 반환하지 않는다."""

    model_config = ConfigDict(extra="ignore")

    title: str = "추천 일정"
    summary: str = ""
    selections: list[RouteSlotSelection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ConfirmedRouteSlot(BaseModel):
    slot_id: str
    day_number: int
    date: date
    start_time: str
    end_date: date | None = None
    end_time: str | None = None
    domain: RouteDomain
    selected: RouteCandidate
    selection_reason: str
    alternatives: list["ConfirmedRouteAlternative"] = Field(
        default_factory=list,
        max_length=ROUTE_FALLBACKS_PER_SLOT,
    )

    @property
    def fallback_candidate_ids(self) -> list[str]:
        return [item.candidate.candidate_id for item in self.alternatives]


class ConfirmedRouteAlternative(BaseModel):
    candidate: RouteCandidate
    selection_reason: str


class ConfirmedRoutePlan(BaseModel):
    title: str
    summary: str
    slots: list[ConfirmedRouteSlot]
    warnings: list[str] = Field(default_factory=list)
    repaired: bool = False
    alternative_routes: list[dict] = Field(default_factory=list, max_length=0)


__all__ = [
    "MAX_ROUTE_DAYS",
    "MAX_SLOTS_PER_DAY",
    "ROUTE_CANDIDATES_PER_SLOT",
    "ROUTE_FALLBACKS_PER_SLOT",
    "RouteDomain",
    "RoutePace",
    "HHMMTime",
    "TripPeriod",
    "TravelPeriod",
    "RouteBudget",
    "RouteRequest",
    "RouteCandidate",
    "RouteSlotCandidates",
    "RoutePlannerInput",
    "RouteSlotSelection",
    "RouteAlternativeSelection",
    "RoutePlannerDraft",
    "ConfirmedRouteSlot",
    "ConfirmedRouteAlternative",
    "ConfirmedRoutePlan",
]
