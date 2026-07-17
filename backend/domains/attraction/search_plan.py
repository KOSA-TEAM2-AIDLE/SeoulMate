from __future__ import annotations

from dataclasses import dataclass
import re

from domains.attraction.taxonomy import categories_for_text
from domains.common.models import DomainSearchRequest


@dataclass(frozen=True)
class AttractionSearchPlan:
    query_text: str
    language: str
    primary_categories: tuple[str, ...]
    secondary_categories: tuple[str, ...]
    event_only: bool
    latitude: float | None
    longitude: float | None
    radius_km: float | None


def build_attraction_search_plan(request: DomainSearchRequest) -> AttractionSearchPlan:
    target_query = request.search_query
    if request.location:
        target_query = re.sub(
            re.escape(request.location),
            " ",
            target_query,
            flags=re.IGNORECASE,
        )
    primary, secondary = categories_for_text([target_query, *request.themes])
    return AttractionSearchPlan(
        query_text=target_query,
        language=request.language,
        primary_categories=primary,
        secondary_categories=secondary,
        event_only="event" in primary,
        latitude=request.latitude,
        longitude=request.longitude,
        radius_km=request.radius_km,
    )
