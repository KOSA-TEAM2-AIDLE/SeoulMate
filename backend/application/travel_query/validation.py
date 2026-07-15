from __future__ import annotations

from copy import deepcopy
from datetime import date
import re
from typing import Any

from application.travel_query.required_info import questions_for_missing_fields
from application.travel_query.state import TravelQueryGraphState


DATE_FIELDS = {"start_date", "end_date", "visit_date"}
TIME_FIELDS = {
    "start_time",
    "end_time",
    "target_time",
    "arrival_at",
    "departure_at",
}
LIST_FIELDS = {
    "requested_domains",
    "themes",
    "transportation",
    "accessibility",
    "required_features",
    "excluded_features",
    "preferred_areas",
    "must_visit",
    "avoid_places",
}


def classify_build_failure(
    state: TravelQueryGraphState,
) -> TravelQueryGraphState:
    """Choose one safe repair, a user question, or a terminal failure."""
    if state.get("repair_attempts", 0) < 1 and _has_safe_format_repair(state):
        return {"status": "repairing"}

    missing_fields = _decision_fields(state)
    if missing_fields:
        return {
            "status": "collecting",
            "missing_fields": missing_fields,
            "assistant_message": questions_for_missing_fields(
                missing_fields,
                state.get("collected", {}),
            ),
            "structured_query": None,
        }

    if state.get("repair_attempts", 0) < 1:
        return {"status": "repairing"}
    return {"status": "failed"}


def repair_confirmed_values(
    state: TravelQueryGraphState,
) -> TravelQueryGraphState:
    """Normalize representation only; never invent a user preference."""
    collected = _normalize_value(deepcopy(state.get("collected", {})))
    intent = state.get("intent")

    start = _as_date(collected.get("start_date"))
    end = _as_date(collected.get("end_date"))
    if intent == "day_trip_route" and start is not None:
        collected.update(
            {
                "start_date": start.isoformat(),
                "end_date": start.isoformat(),
                "days": 1,
                "nights": 0,
            }
        )
    elif intent == "multi_day_route" and start is not None and end is not None:
        days = (end - start).days + 1
        if days > 0:
            collected.update(
                {
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "days": days,
                    "nights": days - 1,
                }
            )

    return {
        "status": "building",
        "collected": collected,
        "repair_attempts": state.get("repair_attempts", 0) + 1,
        "validation_errors": [],
        "structured_query": None,
    }


def _normalize_value(value: Any, field_name: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_value(item, key)
            for key, item in value.items()
        }
    if isinstance(value, list):
        normalized = [_normalize_value(item) for item in value]
        if field_name in LIST_FIELDS:
            return _deduplicate(normalized)
        return normalized
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if field_name in DATE_FIELDS:
        parsed = _as_date(stripped)
        return parsed.isoformat() if parsed is not None else stripped
    if field_name in TIME_FIELDS:
        return _normalize_time(stripped)
    return stripped


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(\d{4})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})", value)
    if not match:
        return None
    try:
        return date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def _normalize_time(value: str) -> str:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", value)
    if not match:
        return value
    hour, minute = (int(part) for part in match.groups())
    if hour > 23 or minute > 59:
        return value
    return f"{hour:02d}:{minute:02d}"


def _deduplicate(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _has_safe_format_repair(state: TravelQueryGraphState) -> bool:
    current = state.get("collected", {})
    return _normalize_value(deepcopy(current)) != current


def _decision_fields(state: TravelQueryGraphState) -> list[str]:
    text = " ".join(state.get("validation_errors", [])).lower()
    intent = state.get("intent")
    fields: list[str] = []

    if "target_places_per_day" in text:
        fields.append("route_request.target_places_per_day")
    if "pace" in text:
        fields.append("route_request.pace")
    if "budget" in text or "예산" in text:
        fields.append("filters.budget_range")
    if any(
        keyword in text
        for keyword in (
            "period",
            "start_date",
            "end_date",
            "visit_date",
            "day_number",
            "days",
            "nights",
            "여행 기간",
        )
    ):
        fields.append(
            "weather_request.target_date"
            if intent == "weather_information"
            else "route_request.period"
        )
    if "destination" in text:
        fields.append("route_request.destination")
    elif "location" in text or "위치" in text:
        fields.append(
            "weather_request.location_name"
            if intent == "weather_information"
            else "filters.location"
        )

    return _deduplicate(fields)[:2]
