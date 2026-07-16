"""첫 GPT의 JSON을 도메인 검색 공통 입력으로 변환한다."""

from domains.common.models import DomainSearchRequest
from schemas.structured_query import StructuredQueryTask, StructuredTravelQuery
from services.query_policy import effective_task_filters


def build_domain_search_request(
    parsed: StructuredTravelQuery,
    task: StructuredQueryTask,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    current_location_name: str | None = None,
    candidate_count: int = 10,
    min_rating: float | None = None,
) -> DomainSearchRequest:
    filters = effective_task_filters(parsed, task)
    required = list(dict.fromkeys([
        *filters.required_features,
        *filters.accessibility,
        *filters.transportation,
    ]))
    return DomainSearchRequest(
        task_id=task.task_id,
        domain=task.domain,
        language=parsed.language,
        search_query=task.search_query,
        themes=task.themes,
        location=filters.location,
        latitude=latitude,
        longitude=longitude,
        current_location_name=current_location_name,
        radius_km=filters.radius_km,
        visit_date=task.visit_date or filters.start_date,
        start_time=task.start_time or filters.time_window,
        end_time=task.end_time,
        party_size=filters.party_size,
        budget_min_krw=filters.budget_min_krw,
        budget_max_krw=filters.budget_max_krw,
        min_rating=min_rating,
        required_features=required,
        excluded_features=filters.excluded_features,
        candidate_count=max(candidate_count, task.desired_count),
        context={"parsed_query": parsed, "task": task},
    )


__all__ = ["build_domain_search_request"]

