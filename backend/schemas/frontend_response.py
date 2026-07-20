"""SSE meta 안의 ``result``로 프론트에 전달하는 최종 화면 DTO."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrontendPlace(BaseModel):
    """상세 API ID와 화면 표시용으로 검증된 최소 장소 정보."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    slotId: str | None = None
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    subCategory: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    rating: str | None = None
    reviews: str | None = None
    time: str | None = None
    image: str | None = None
    selectionReason: str | None = None
    link: str | None = None
    price: str | None = None
    live_rating: str | None = None
    features: str | None = None
    alternatives: list["FrontendPlace"] = Field(default_factory=list, max_length=2)


FrontendResponseType = Literal[
    "route",
    "recommendation",
    "weather",
    "general",
    "error",
]


class FrontendResponse(BaseModel):
    """프론트가 responseType만 보고 안전하게 분기할 수 있는 최종 계약."""

    model_config = ConfigDict(extra="forbid")

    responseType: FrontendResponseType
    day: int | None = Field(default=None, ge=1)
    allDay: int | None = Field(default=None, ge=1)
    travelPath: dict[str, list[FrontendPlace]] | None = None
    accommodation: FrontendPlace | None = None
    recommendList: list[FrontendPlace] | None = Field(default=None, max_length=3)

    @model_validator(mode="after")
    def validate_exclusive_payload(self):
        if self.responseType == "route":
            if self.travelPath is None or self.recommendList is not None:
                raise ValueError("route 응답은 travelPath만 가져야 합니다.")
            if self.day is None or self.allDay is None:
                raise ValueError("route 응답은 day와 allDay가 필요합니다.")
            if self.allDay != len(self.travelPath):
                raise ValueError("allDay는 travelPath의 일차 개수와 같아야 합니다.")
            if self.day > self.allDay:
                raise ValueError("day는 allDay를 초과할 수 없습니다.")
            if self.accommodation is not None and self.allDay < 2:
                raise ValueError("숙소 분리 응답은 다일 일정에서만 사용할 수 있습니다.")
            expected_keys = {str(value) for value in range(1, self.allDay + 1)}
            if set(self.travelPath) != expected_keys:
                raise ValueError("travelPath 키는 1부터 allDay까지 연속이어야 합니다.")
        elif self.responseType == "recommendation":
            if (
                self.travelPath is not None
                or self.accommodation is not None
                or self.recommendList is None
            ):
                raise ValueError("recommendation 응답은 recommendList만 가져야 합니다.")
            if self.day is not None or self.allDay is not None:
                raise ValueError("recommendation 응답의 day와 allDay는 null이어야 합니다.")
        else:
            if any(value is not None for value in (
                self.day,
                self.allDay,
                self.travelPath,
                self.accommodation,
                self.recommendList,
            )):
                raise ValueError("장소 응답이 아닌 경우 장소 관련 필드는 모두 null이어야 합니다.")
        return self


__all__ = ["FrontendPlace", "FrontendResponse", "FrontendResponseType"]
