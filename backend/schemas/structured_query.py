"""고정 GPT Structured Query 출력 계약. 프롬프트를 바꾸지 않고 이 스키마를 소비한다."""

from __future__ import annotations

from datetime import date, timedelta
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.route_planner import RouteRequest


Domain = Literal["cafe", "restaurant", "accommodation", "attraction", "etc", "weather"]
SINGLE_RECOMMENDATION_CHOICES = 3
TravelIntent = Literal[
    "multi_day_route",
    "day_trip_route",
    "single_place_recommendation",
    "weather_information",
    "general_response",
]


class StructuredSearchFilters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    location: str | None = None
    radius_km: float | None = Field(default=None, gt=0, le=100)
    is_active: bool | None = None
    start_date: date | None = None
    end_date: date | None = None
    time_window: str | None = None
    party_size: int | None = Field(default=None, ge=1, le=100)
    budget_min_krw: int | None = Field(default=None, ge=0)
    budget_max_krw: int | None = Field(default=None, ge=0)
    transportation: list[str] = Field(default_factory=list)
    accessibility: list[str] = Field(default_factory=list)
    required_features: list[str] = Field(default_factory=list)
    excluded_features: list[str] = Field(default_factory=list)

    @field_validator(
        "transportation",
        "accessibility",
        "required_features",
        "excluded_features",
        mode="before",
    )
    @classmethod
    def normalize_optional_lists(cls, value):
        return [] if value is None else value

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date는 end_date보다 늦을 수 없습니다.")
        if (
            self.budget_min_krw is not None
            and self.budget_max_krw is not None
            and self.budget_min_krw > self.budget_max_krw
        ):
            raise ValueError("budget_min_krw는 budget_max_krw보다 클 수 없습니다.")
        return self


class StructuredQueryTask(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(min_length=1)
    domain: Domain
    search_query: str = Field(min_length=1)
    themes: list[str] = Field(default_factory=list)
    desired_count: int = Field(default=1, ge=1, le=20)
    notes: str | None = None
    # 루트 요청에서는 하나의 Task가 하나의 방문 슬롯을 뜻한다.
    slot_id: str | None = None
    day_number: int | None = Field(default=None, ge=1, le=7)
    visit_date: date | None = None
    start_time: str | None = None
    end_date: date | None = None
    end_time: str | None = None
    # 서로 다른 지역·시간을 한 질문에서 요청할 때만 사용한다. 값이 없는 필드는
    # TravelQuery.filters를 상속하므로 기존 JSON과 완전히 호환된다.
    filters: StructuredSearchFilters | None = Field(
        default=None,
        description=(
            "이 Task에만 적용되는 지역·날짜·시간·예산·시설 조건. 서로 다른 Task가 "
            "서로 다른 지역이나 조건을 가지면 반드시 채우고, 공통 조건이면 null."
        ),
    )

    @field_validator("themes", mode="before")
    @classmethod
    def normalize_optional_themes(cls, value):
        return [] if value is None else value

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_clock_time(cls, value: str | None):
        if value is None:
            return value
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
        if not match:
            raise ValueError("시간은 HH:MM 형식이어야 합니다.")
        hour, minute = map(int, match.groups())
        if hour > 23 or minute > 59:
            raise ValueError("시간 범위가 올바르지 않습니다.")
        return f"{hour:02d}:{minute:02d}"

    @model_validator(mode="after")
    def validate_visit_interval(self):
        if self.visit_date and self.end_date and self.end_date < self.visit_date:
            raise ValueError("end_date는 visit_date보다 빠를 수 없습니다.")
        if (
            self.start_time
            and self.end_time
            and (self.end_date is None or self.end_date == self.visit_date)
            and self.end_time <= self.start_time
        ):
            raise ValueError("같은 날짜의 end_time은 start_time보다 늦어야 합니다.")
        return self


class StructuredWeatherRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str = Field(min_length=1)
    location_name: str | None = None
    target_date: date | None = None
    target_time: str | None = None
    language: str = "ko"


class StructuredTravelQuery(BaseModel):
    """현재 고정 프롬프트가 반환하는 JSON과 이후 확장 필드를 모두 안전하게 수용한다."""

    model_config = ConfigDict(extra="ignore")

    language: str = "ko"
    intent: TravelIntent
    original_question: str = Field(min_length=1)
    normalized_question: str = Field(min_length=1)
    tasks: list[StructuredQueryTask] = Field(default_factory=list, max_length=35)
    filters: StructuredSearchFilters = Field(
        default_factory=StructuredSearchFilters,
        description="모든 Task에 공통으로 적용되는 조건. Task마다 다르면 각 task.filters 사용.",
    )
    # 다일/당일 루트 요청의 명시적 계약.
    route_request: RouteRequest | None = None
    general_response_instruction: str | None = None
    # 일부 노트북 버전이 반환하면 사용하고, 없으면 코드 정책으로 파생한다.
    source_mode: Literal["rag_only", "rag_mcp", "mcp_only"] | None = None
    weather_request: StructuredWeatherRequest | None = None

    @field_validator("tasks", mode="before")
    @classmethod
    def normalize_optional_tasks(cls, value):
        return [] if value is None else value

    @field_validator("filters", mode="before")
    @classmethod
    def normalize_optional_filters(cls, value):
        return {} if value is None else value

    @model_validator(mode="after")
    def validate_unique_task_ids(self):
        # 일부 GPT 응답은 weather_request와 별도로 domain=weather Task도 만든다.
        # 날씨는 장소 검색 도메인이 아니므로 검증 단계에서 안전하게 제거한다.
        self.tasks = [task for task in self.tasks if task.domain != "weather"]
        if self.intent in {"weather_information", "general_response"} and self.tasks:
            raise ValueError(f"{self.intent}에서는 장소 Task를 만들 수 없습니다.")
        if self.intent == "weather_information" and self.source_mode not in {None, "mcp_only"}:
            raise ValueError("weather_information의 source_mode는 mcp_only여야 합니다.")
        if self.intent == "general_response" and self.source_mode is not None:
            raise ValueError("general_response의 source_mode는 null이어야 합니다.")
        if (
            self.intent in {"single_place_recommendation", "day_trip_route", "multi_day_route"}
            and self.source_mode == "mcp_only"
        ):
            raise ValueError("장소 검색 intent에는 mcp_only를 사용할 수 없습니다.")
        if self.intent in {"day_trip_route", "multi_day_route"} and self.route_request:
            period = self.route_request.period
            if self.intent == "day_trip_route" and period.days != 1:
                raise ValueError("day_trip_route의 여행 기간은 1일이어야 합니다.")
            if self.intent == "multi_day_route" and period.days < 2:
                raise ValueError("multi_day_route의 여행 기간은 2일 이상이어야 합니다.")
            current_day = 1
            previous_domain: Domain | None = None
            slot_counts: dict[tuple[int, str], int] = {}
            normalized_route_tasks: list[StructuredQueryTask] = []
            for task in self.tasks:
                if task.day_number is not None:
                    if task.day_number > period.days:
                        raise ValueError("Task day_number가 여행 기간을 벗어났습니다.")
                    day_number = task.day_number
                elif task.visit_date is not None:
                    if not period.start_date <= task.visit_date <= period.end_date:
                        raise ValueError("Task visit_date가 여행 기간을 벗어났습니다.")
                    day_number = (task.visit_date - period.start_date).days + 1
                elif (
                    self.intent == "multi_day_route"
                    and previous_domain == "accommodation"
                ):
                    day_number = min(current_day + 1, period.days)
                else:
                    day_number = current_day
                current_day = day_number
                visit_date = period.start_date + timedelta(days=day_number - 1)
                slot_key = (day_number, task.domain)
                slot_counts[slot_key] = slot_counts.get(slot_key, 0) + 1
                slot_id = task.slot_id or (
                    f"d{day_number}-{task.domain}-{slot_counts[slot_key]}"
                )
                task = task.model_copy(update={
                    "slot_id": slot_id,
                    "day_number": day_number,
                    "visit_date": visit_date,
                    "desired_count": 1,
                })
                normalized_route_tasks.append(task)
                previous_domain = task.domain
            self.tasks = normalized_route_tasks
            slot_ids = [task.slot_id for task in self.tasks]
            if len(slot_ids) != len(set(slot_ids)):
                raise ValueError("루트 slot_id는 중복될 수 없습니다.")
            per_day: dict[int, int] = {}
            for task in self.tasks:
                per_day[task.day_number] = per_day.get(task.day_number, 0) + 1
            if any(count > self.route_request.max_places_per_day for count in per_day.values()):
                raise ValueError("하루 Task 수가 max_places_per_day를 초과했습니다.")
            if self.intent == "multi_day_route":
                missing_days = [
                    day for day in range(1, period.days + 1)
                    if per_day.get(day, 0) == 0
                ]
                if missing_days:
                    raise ValueError(
                        "multi_day_route에는 모든 여행 일차의 Task가 필요합니다: "
                        f"누락 Day {missing_days}"
                    )
            if (
                self.intent == "day_trip_route"
                and self.route_request.target_places_per_day is not None
                and len(self.tasks) != self.route_request.target_places_per_day
            ):
                raise ValueError(
                    "당일 루트의 Task 수는 route_request.target_places_per_day와 "
                    "일치해야 합니다."
                )
        if self.intent == "multi_day_route":
            normalized_tasks: list[StructuredQueryTask] = []
            for task in self.tasks:
                if task.domain == "accommodation" and task.visit_date:
                    task = task.model_copy(update={
                        "end_date": task.end_date or (task.visit_date + timedelta(days=1)),
                        "end_time": task.end_time or "08:00",
                    })
                normalized_tasks.append(task)
            self.tasks = normalized_tasks
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task_id는 요청 안에서 중복될 수 없습니다.")
        if self.intent not in {"day_trip_route", "multi_day_route"} and len(self.tasks) > 5:
            raise ValueError("일반 추천 Task는 최대 5개입니다.")
        # 제품 정책: 단일 장소 추천은 사용자가 "한 곳"이라고 표현해도 비교 가능한
        # 선택지 3개를 제공한다. 루트 Task는 슬롯당 대표 1곳을 뽑으므로 변경하지 않는다.
        if self.intent == "single_place_recommendation":
            if not self.tasks:
                raise ValueError("single_place_recommendation에는 장소 Task가 필요합니다.")
            self.tasks = [
                task.model_copy(update={"desired_count": SINGLE_RECOMMENDATION_CHOICES})
                for task in self.tasks
            ]
        return self


__all__ = [
    "StructuredQueryTask",
    "StructuredSearchFilters",
    "StructuredTravelQuery",
    "StructuredWeatherRequest",
    "RouteRequest",
    "SINGLE_RECOMMENDATION_CHOICES",
]
