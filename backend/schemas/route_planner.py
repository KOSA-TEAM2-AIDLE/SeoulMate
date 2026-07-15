from datetime import date, time
from typing import Annotated, Literal, Self
from pydantic import BaseModel, Field, PlainSerializer, model_validator

RoutePace = Literal["relaxed", "normal", "packed"]
HHMMTime = Annotated[
    time,
    PlainSerializer(
        lambda value: value.strftime("%H:%M"),
        return_type=str,
        when_used="json",
    ),
]


class TravelPeriod(BaseModel):
    start_date: date
    end_date: date
    nights: int = Field(ge=0)
    days: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        calculated_days = (self.end_date - self.start_date).days + 1
        if calculated_days <= 0:
            raise ValueError("end_date는 start_date보다 빠를 수 없습니다.")
        if self.days != calculated_days:
            raise ValueError("days가 시작일과 종료일의 날짜 범위와 다릅니다.")
        if self.nights != self.days - 1:
            raise ValueError("nights는 days보다 1 작아야 합니다.")
        return self


class RouteRequest(BaseModel):
    destination: str = Field(min_length=1)
    period: TravelPeriod
    adults: int = Field(default=1, ge=1)
    children: int = Field(default=0, ge=0)
    arrival_at: HHMMTime | None = None
    arrival_location: str | None = None
    departure_at: HHMMTime | None = None
    departure_location: str | None = None
    pace: RoutePace = "normal"
    max_places_per_day: int = Field(default=5, ge=1, le=5)
    target_places_per_day: int | None = Field(default=None, ge=1, le=5)
    transportation: list[str] = Field(default_factory=list)
    preferred_areas: list[str] = Field(default_factory=list)
    preferred_themes: list[str] = Field(default_factory=list)
    required_features: list[str] = Field(default_factory=list)
    excluded_features: list[str] = Field(default_factory=list)
    must_visit: list[str] = Field(default_factory=list)
    avoid_places: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_place_limits(self) -> Self:
        if (
            self.target_places_per_day is not None
            and self.target_places_per_day > self.max_places_per_day
        ):
            raise ValueError(
                "target_places_per_day는 max_places_per_day보다 클 수 없습니다."
            )
        return self
