from collections import Counter
from datetime import date
from typing import Any, Literal, Self
from pydantic import BaseModel, Field, field_validator, model_validator
from schemas.route_planner import HHMMTime, RouteRequest

TravelIntent = Literal[
    "single_place_recommendation",
    "day_trip_route",
    "multi_day_route",
    "modify_route",
    "weather_information",
    "general_response",
]
TaskDomain = Literal[
    "restaurant",
    "cafe",
    "accommodation",
    "attraction",
    "etc",
]
SourceMode = Literal["rag_only", "rag_mcp", "mcp_only"]


class TimeWindow(BaseModel):
    start_time: HHMMTime | None = None
    end_time: HHMMTime | None = None


class QueryFilters(BaseModel):
    location: str | None = None
    radius_km: float | None = Field(default=None, gt=0)
    is_active: bool | None = None
    start_date: date | None = None
    end_date: date | None = None
    time_window: TimeWindow | None = None
    party_size: int | None = Field(default=None, ge=1)
    budget_min_krw: int | None = Field(default=None, ge=0)
    budget_max_krw: int | None = Field(default=None, ge=0)
    transportation: list[str] = Field(default_factory=list)
    accessibility: list[str] = Field(default_factory=list)
    required_features: list[str] = Field(default_factory=list)
    excluded_features: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("filters.end_date는 start_date보다 빠를 수 없습니다.")
        if (
            self.budget_min_krw is not None
            and self.budget_max_krw is not None
            and self.budget_max_krw < self.budget_min_krw
        ):
            raise ValueError("최대 예산은 최소 예산보다 작을 수 없습니다.")
        return self


class TravelTask(BaseModel):
    task_id: str = Field(min_length=1)
    domain: TaskDomain
    search_query: str = Field(min_length=1)
    themes: list[str] = Field(default_factory=list)
    desired_count: int = Field(ge=1)
    notes: str | None = None
    slot_id: str | None = None
    day_number: int | None = Field(default=None, ge=1)
    visit_date: date | None = None
    start_time: HHMMTime | None = None
    end_date: date | None = None
    end_time: HHMMTime | None = None
    filters: QueryFilters | None = None

    @field_validator("task_id", "search_query")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("필수 문자열은 공백일 수 없습니다.")
        return value


class WeatherRequest(BaseModel):
    query: str = Field(min_length=1)
    location_name: str = Field(min_length=1)
    target_date: date
    target_time: HHMMTime | None = None
    language: Literal["ko", "en"] = "ko"


class StructuredTravelQuery(BaseModel):
    language: Literal["ko", "en"] = "ko"
    intent: TravelIntent
    original_question: str = Field(min_length=1)
    normalized_question: str = Field(min_length=1)
    tasks: list[TravelTask]
    filters: QueryFilters
    source_mode: SourceMode | None = None
    weather_request: WeatherRequest | None = None
    route_request: RouteRequest | None = None
    route_context: dict[str, Any] | None = None
    general_response_instruction: str | None = None

    @model_validator(mode="before")
    @classmethod
    def apply_product_policies(cls, value: Any) -> Any:
        """LLM 출력 전에 확정된 규정을 적용한다."""
        if not isinstance(value, dict):
            return value

        normalized = value.copy()
        intent = value.get("intent")

        if intent == "single_place_recommendation":
            tasks: list[Any] = []
            for task in value.get("tasks", []):
                if isinstance(task, dict):
                    normalized_task = task.copy()
                    normalized_task["desired_count"] = 3
                    tasks.append(normalized_task)
                elif isinstance(task, TravelTask):
                    tasks.append(task.model_copy(update={"desired_count": 3}))
                else:
                    tasks.append(task)
            normalized["tasks"] = tasks

        place_intents = {
            "single_place_recommendation",
            "day_trip_route",
            "multi_day_route",
            "modify_route",
        }
        filters = value.get("filters")
        if intent in place_intents and isinstance(filters, dict):
            normalized_filters = filters.copy()
            if normalized_filters.get("is_active") is None:
                normalized_filters["is_active"] = True
            normalized["filters"] = normalized_filters
        return normalized

    @field_validator("original_question", "normalized_question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("질문은 공백일 수 없습니다.")
        return value

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task_id는 요청 안에서 중복될 수 없습니다.")

        slot_ids = [task.slot_id for task in self.tasks if task.slot_id]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("slot_id는 요청 안에서 중복될 수 없습니다.")

        if self.intent == "single_place_recommendation":
            if not self.tasks:
                raise ValueError("단일 장소 추천에는 하나 이상의 Task가 필요합니다.")

        if self.intent in {"day_trip_route", "multi_day_route"}:
            self._validate_route_tasks()

        if self.intent == "day_trip_route":
            if self.route_request.period.days != 1:
                raise ValueError("당일 루트의 여행 기간은 1일이어야 합니다.")
            target = self.route_request.target_places_per_day
            if target is None:
                raise ValueError("당일 루트에는 target_places_per_day가 필요합니다.")
            if target != len(self.tasks):
                raise ValueError(
                    "당일 루트의 Task 수와 target_places_per_day가 같아야 합니다."
                )

        if self.intent == "multi_day_route":
            if self.route_request.period.days < 2:
                raise ValueError("다일 루트의 여행 기간은 2일 이상이어야 합니다.")
            if len(self.tasks) > 35:
                raise ValueError("다일 루트의 전체 Task는 최대 35개입니다.")
            counts = Counter(
                task.day_number
                for task in self.tasks
                if task.day_number is not None
            )
            if any(
                count > self.route_request.max_places_per_day
                for count in counts.values()
            ):
                raise ValueError("다일 루트의 일별 Task 수가 허용 범위를 벗어났습니다.")

        if self.intent == "modify_route":
            if len(self.tasks) != 1 or self.tasks[0].desired_count != 1:
                raise ValueError("루트 수정에는 교체 대상 Task 한 개가 필요합니다.")

        if self.intent == "weather_information":
            if self.tasks:
                raise ValueError("날씨 조회에는 장소 Task를 만들 수 없습니다.")
            if self.weather_request is None:
                raise ValueError("날씨 조회에는 weather_request가 필요합니다.")

        if self.intent == "general_response" and self.tasks:
            raise ValueError("일반 응답에는 장소 Task를 만들 수 없습니다.")

        route_intents = {"day_trip_route", "multi_day_route"}
        if self.intent not in route_intents and self.route_request is not None:
            raise ValueError("route_request는 당일·다일 루트에서만 사용할 수 있습니다.")

        if self.intent == "general_response":
            if not self.general_response_instruction:
                raise ValueError(
                    "일반 응답에는 general_response_instruction이 필요합니다."
                )
        elif self.general_response_instruction is not None:
            raise ValueError(
                "general_response_instruction은 일반 응답에서만 사용할 수 있습니다."
            )

        return self

    def _validate_route_tasks(self) -> None:
        if self.route_request is None:
            raise ValueError("루트 intent에는 route_request가 필요합니다.")
        if not self.tasks:
            raise ValueError("루트 intent에는 하나 이상의 Task가 필요합니다.")
        if any(task.desired_count != 1 for task in self.tasks):
            raise ValueError("루트 Task의 desired_count는 1이어야 합니다.")
        period = self.route_request.period
        for task in self.tasks:
            if (task.day_number is None) != (task.visit_date is None):
                raise ValueError(
                    "day_number와 visit_date는 함께 제공하거나 함께 생략해야 합니다."
                )
            if task.visit_date is None:
                continue
            expected_day = (task.visit_date - period.start_date).days + 1
            if not period.start_date <= task.visit_date <= period.end_date:
                raise ValueError("Task 방문일이 여행 기간을 벗어났습니다.")
            if task.day_number is not None and task.day_number != expected_day:
                raise ValueError("Task의 day_number와 visit_date가 일치하지 않습니다.")
