"""첫 GPT와 추천·루트 백엔드가 공유하는 StructuredTravelQuery 계약."""

from __future__ import annotations

from collections import Counter
from datetime import date, time, timedelta
import re
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.route_planner import RouteRequest


TaskDomain = Literal["cafe", "restaurant", "accommodation", "attraction", "etc"]
Domain = TaskDomain | Literal["weather"]
SourceMode = Literal["rag_only", "rag_mcp", "mcp_only"]
TravelIntent = Literal[
    "multi_day_route",
    "day_trip_route",
    "single_place_recommendation",
    "modify_route",
    "weather_information",
    "general_response",
]
SINGLE_RECOMMENDATION_CHOICES = 3


class TimeWindow(BaseModel):
    start_time: str | None = None
    end_time: str | None = None


class StructuredSearchFilters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    location: str | None = None
    radius_km: float | None = Field(default=None, gt=0, le=100)
    is_active: bool | None = None
    start_date: date | None = None
    end_date: date | None = None
    time_window: str | TimeWindow | None = None
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


# 첫 GPT 구현에서 사용한 이름과 develop의 소비자 이름을 모두 지원한다.
QueryFilters = StructuredSearchFilters


class StructuredQueryTask(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(min_length=1)
    domain: Domain
    search_query: str = Field(min_length=1)
    themes: list[str] = Field(default_factory=list)
    desired_count: int = Field(default=1, ge=1, le=20)
    notes: str | None = None
    slot_id: str | None = None
    day_number: int | None = Field(default=None, ge=1, le=7)
    visit_date: date | None = None
    start_time: str | None = None
    end_date: date | None = None
    end_time: str | None = None
    filters: StructuredSearchFilters | None = None

    @field_validator("themes", mode="before")
    @classmethod
    def normalize_optional_themes(cls, value):
        return [] if value is None else value

    @field_validator("task_id", "search_query")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("필수 문자열은 공백일 수 없습니다.")
        return value

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


TravelTask = StructuredQueryTask


class StructuredWeatherRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str = Field(min_length=1)
    location_name: str | None = None
    target_date: date | None = None
    target_time: str | None = None
    language: str = "ko"

    @field_validator("target_time")
    @classmethod
    def validate_target_time(cls, value: str | None):
        if value is None:
            return value
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
        if not match:
            raise ValueError("시간은 HH:MM 형식이어야 합니다.")
        hour, minute = map(int, match.groups())
        if hour > 23 or minute > 59:
            raise ValueError("시간 범위가 올바르지 않습니다.")
        return f"{hour:02d}:{minute:02d}"


WeatherRequest = StructuredWeatherRequest


class StructuredTravelQuery(BaseModel):
    """확정된 사용자 의도를 추천 및 루트 계층에 전달하는 최종 JSON."""

    model_config = ConfigDict(extra="ignore")

    language: str = "ko"
    intent: TravelIntent
    original_question: str = Field(min_length=1)
    normalized_question: str = Field(min_length=1)
    tasks: list[StructuredQueryTask] = Field(default_factory=list, max_length=35)
    filters: StructuredSearchFilters = Field(default_factory=StructuredSearchFilters)
    source_mode: SourceMode | None = None
    weather_request: StructuredWeatherRequest | None = None
    route_request: RouteRequest | None = None
    general_response_instruction: str | None = None

    @model_validator(mode="before")
    @classmethod
    def apply_product_policies(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = value.copy()
        intent = normalized.get("intent")
        if intent == "single_place_recommendation":
            normalized["tasks"] = [
                {**task, "desired_count": SINGLE_RECOMMENDATION_CHOICES}
                if isinstance(task, dict)
                else task.model_copy(update={"desired_count": SINGLE_RECOMMENDATION_CHOICES})
                if isinstance(task, StructuredQueryTask)
                else task
                for task in (normalized.get("tasks") or [])
            ]
        if intent in {
            "single_place_recommendation",
            "day_trip_route",
            "multi_day_route",
            "modify_route",
        }:
            filters = normalized.get("filters")
            if filters is None:
                filters = {}
            if isinstance(filters, dict):
                filters = filters.copy()
                filters.setdefault("is_active", True)
                normalized["filters"] = filters
        return normalized

    @field_validator("tasks", mode="before")
    @classmethod
    def normalize_optional_tasks(cls, value):
        return [] if value is None else value

    @field_validator("filters", mode="before")
    @classmethod
    def normalize_optional_filters(cls, value):
        return {} if value is None else value

    @field_validator("original_question", "normalized_question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("질문은 공백일 수 없습니다.")
        return value

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        self.tasks = [task for task in self.tasks if task.domain != "weather"]
        self._validate_intent_sources()
        self._validate_task_identity()

        if self.intent == "single_place_recommendation":
            if not self.tasks:
                raise ValueError("single_place_recommendation에는 장소 Task가 필요합니다.")
            self.tasks = [
                task.model_copy(update={"desired_count": SINGLE_RECOMMENDATION_CHOICES})
                for task in self.tasks
            ]

        if self.intent in {"day_trip_route", "multi_day_route"}:
            if self.route_request is not None:
                self._validate_and_normalize_route_tasks()
            else:
                self._normalize_legacy_route_tasks()

        if self.intent == "modify_route":
            if len(self.tasks) != 1 or self.tasks[0].desired_count != 1:
                raise ValueError("루트 수정에는 교체 대상 Task 한 개가 필요합니다.")

        if self.intent == "weather_information":
            if self.tasks:
                raise ValueError("weather_information에서는 장소 Task를 만들 수 없습니다.")

        if self.intent == "general_response":
            if self.tasks:
                raise ValueError("general_response에서는 장소 Task를 만들 수 없습니다.")
            if not self.general_response_instruction:
                raise ValueError(
                    "general_response에는 general_response_instruction이 필요합니다."
                )
        elif self.general_response_instruction is not None:
            raise ValueError(
                "general_response_instruction은 general_response에서만 사용할 수 있습니다."
            )

        if self.intent not in {"day_trip_route", "multi_day_route"}:
            if self.route_request is not None:
                raise ValueError("route_request는 당일·다일 루트에서만 사용할 수 있습니다.")
        return self

    def _validate_intent_sources(self) -> None:
        if self.intent in {"weather_information", "general_response"} and self.tasks:
            raise ValueError(f"{self.intent}에서는 장소 Task를 만들 수 없습니다.")
        if self.intent == "weather_information" and self.source_mode not in {
            None,
            "mcp_only",
        }:
            raise ValueError("weather_information의 source_mode는 mcp_only여야 합니다.")
        if self.intent == "general_response" and self.source_mode is not None:
            raise ValueError("general_response의 source_mode는 null이어야 합니다.")
        if (
            self.intent
            in {"single_place_recommendation", "day_trip_route", "multi_day_route"}
            and self.source_mode == "mcp_only"
        ):
            raise ValueError("장소 검색 intent에는 mcp_only를 사용할 수 없습니다.")

    def _validate_task_identity(self) -> None:
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task_id는 요청 안에서 중복될 수 없습니다.")
        slot_ids = [task.slot_id for task in self.tasks if task.slot_id]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("루트 slot_id는 중복될 수 없습니다.")
        if self.intent not in {"day_trip_route", "multi_day_route"} and len(self.tasks) > 5:
            raise ValueError("일반 추천 Task는 최대 5개입니다.")

    def _validate_and_normalize_route_tasks(self) -> None:
        assert self.route_request is not None
        if not self.tasks:
            raise ValueError("루트 intent에는 하나 이상의 Task가 필요합니다.")

        period = self.route_request.period
        if self.intent == "day_trip_route" and period.days != 1:
            raise ValueError("day_trip_route의 여행 기간은 1일이어야 합니다.")
        if self.intent == "multi_day_route" and period.days < 2:
            raise ValueError("multi_day_route의 여행 기간은 2일 이상이어야 합니다.")

        normalized_tasks: list[StructuredQueryTask] = []
        current_day = 1
        previous_domain: Domain | None = None
        slot_counts: dict[tuple[int, str], int] = {}

        for task in self.tasks:
            if self.intent == "day_trip_route":
                normalized_tasks.append(self._validate_day_task(task, period.start_date))
                continue

            day_number = self._multi_day_number(task, period, current_day, previous_domain)
            visit_date = period.start_date + timedelta(days=day_number - 1)
            slot_key = (day_number, task.domain)
            slot_counts[slot_key] = slot_counts.get(slot_key, 0) + 1
            task = task.model_copy(
                update={
                    "slot_id": task.slot_id
                    or f"d{day_number}-{task.domain}-{slot_counts[slot_key]}",
                    "day_number": day_number,
                    "visit_date": visit_date,
                    "desired_count": 1,
                }
            )
            if task.domain == "accommodation":
                task = task.model_copy(
                    update={
                        "end_date": task.end_date or (visit_date + timedelta(days=1)),
                        "end_time": task.end_time or "08:00",
                    }
                )
            normalized_tasks.append(task)
            current_day = day_number
            previous_domain = task.domain

        self.tasks = normalized_tasks
        self._validate_route_time_bounds()
        counts = Counter(task.day_number or 1 for task in self.tasks)
        if any(count > self.route_request.max_places_per_day for count in counts.values()):
            raise ValueError("하루 Task 수가 max_places_per_day를 초과했습니다.")

        if self.intent == "day_trip_route":
            target = self.route_request.target_places_per_day
            if target is not None and len(self.tasks) != target:
                raise ValueError(
                    "당일 루트의 Task 수와 route_request.target_places_per_day는 "
                    "일치해야 합니다."
                )
        else:
            missing_days = [
                day for day in range(1, period.days + 1) if counts.get(day, 0) == 0
            ]
            if missing_days:
                raise ValueError(
                    "multi_day_route에는 모든 여행 일차의 Task가 필요합니다: "
                    f"누락 Day {missing_days}"
                )

    def _validate_route_time_bounds(self) -> None:
        assert self.route_request is not None
        period = self.route_request.period
        arrival_at = self.route_request.arrival_at
        departure_at = self.route_request.departure_at
        for task in self.tasks:
            if task.start_time is None or task.day_number is None:
                continue
            start_time = time.fromisoformat(task.start_time)
            if task.day_number == 1 and arrival_at is not None and start_time < arrival_at:
                raise ValueError("첫날 Task는 arrival_at보다 빠를 수 없습니다.")
            if task.day_number != period.days or departure_at is None:
                continue
            if start_time >= departure_at:
                raise ValueError("마지막 날 Task는 departure_at 전에 시작해야 합니다.")
            effective_end_date = task.end_date or task.visit_date
            if (
                task.end_time is not None
                and effective_end_date == period.end_date
                and time.fromisoformat(task.end_time) > departure_at
            ):
                raise ValueError("마지막 날 Task는 departure_at까지 끝나야 합니다.")

    def _normalize_legacy_route_tasks(self) -> None:
        """route_request 도입 전 요청은 라우터의 기간 보완 로직에 맡긴다."""
        if not self.tasks:
            raise ValueError("루트 intent에는 하나 이상의 Task가 필요합니다.")
        normalized: list[StructuredQueryTask] = []
        for task in self.tasks:
            task = task.model_copy(update={"desired_count": 1})
            if (
                self.intent == "multi_day_route"
                and task.domain == "accommodation"
                and task.visit_date is not None
            ):
                task = task.model_copy(
                    update={
                        "end_date": task.end_date
                        or (task.visit_date + timedelta(days=1)),
                        "end_time": task.end_time or "08:00",
                    }
                )
            normalized.append(task)
        self.tasks = normalized

    @staticmethod
    def _validate_day_task(
        task: StructuredQueryTask,
        expected_date: date,
    ) -> StructuredQueryTask:
        if (task.day_number is None) != (task.visit_date is None):
            raise ValueError("day_number와 visit_date는 함께 제공하거나 함께 생략해야 합니다.")
        if task.day_number is not None and task.day_number != 1:
            raise ValueError("당일 Task의 day_number는 1이어야 합니다.")
        if task.visit_date is not None and task.visit_date != expected_date:
            raise ValueError("Task visit_date가 여행 기간과 일치하지 않습니다.")
        return task.model_copy(update={"desired_count": 1})

    @staticmethod
    def _multi_day_number(
        task: StructuredQueryTask,
        period,
        current_day: int,
        previous_domain: Domain | None,
    ) -> int:
        if task.day_number is not None and task.visit_date is not None:
            expected = (task.visit_date - period.start_date).days + 1
            if expected != task.day_number:
                raise ValueError("Task의 day_number와 visit_date가 일치하지 않습니다.")
        if task.day_number is not None:
            day_number = task.day_number
        elif task.visit_date is not None:
            day_number = (task.visit_date - period.start_date).days + 1
        elif previous_domain == "accommodation":
            day_number = min(current_day + 1, period.days)
        else:
            day_number = current_day
        if not 1 <= day_number <= period.days:
            raise ValueError("Task day_number 또는 visit_date가 여행 기간을 벗어났습니다.")
        return day_number


__all__ = [
    "TaskDomain",
    "Domain",
    "SourceMode",
    "TravelIntent",
    "TimeWindow",
    "StructuredQueryTask",
    "TravelTask",
    "StructuredSearchFilters",
    "QueryFilters",
    "StructuredTravelQuery",
    "StructuredWeatherRequest",
    "WeatherRequest",
    "RouteRequest",
    "SINGLE_RECOMMENDATION_CHOICES",
]
