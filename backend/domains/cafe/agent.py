from application.recommendation.request_factory import build_domain_search_request
from domains.cafe.search_service import CafeSearchService
from domains.common.search_interface import DomainSearchService
from schemas.travel_query_api import (
    DomainAgentDispatchResult,
    TravelQueryApiResponse,
)


class CafeAgent:
    """구조화된 여행 질의에서 카페 Task를 골라 후보를 검색한다."""

    domain = "cafe"

    def __init__(
        self,
        search_service: DomainSearchService | None = None,
    ) -> None:
        self.search_service = search_service or CafeSearchService()

    async def execute(
        self,
        response: TravelQueryApiResponse,
    ) -> DomainAgentDispatchResult:
        if response.status != "ready":
            raise ValueError("ready 상태에서만 카페 에이전트를 실행할 수 있습니다.")

        query = response.structured_query
        if query is None:
            raise ValueError("structured_query가 없습니다.")

        cafe_tasks = [
            task
            for task in query.tasks
            if task.domain == self.domain
        ]
        candidates = []
        for task in cafe_tasks:
            request = build_domain_search_request(
                query,
                task,
                latitude=response.current_latitude,
                longitude=response.current_longitude,
                current_location_name=response.current_location_name,
                candidate_count=max(5, task.desired_count),
            )
            candidates.extend(await self.search_service.search(request))

        return DomainAgentDispatchResult(
            domain=self.domain,
            status="completed",
            task_ids=[task.task_id for task in cafe_tasks],
            candidates=candidates,
            assistant_message=(
                f"카페 에이전트가 {len(cafe_tasks)}개 Task에서 "
                f"{len(candidates)}개의 후보를 검색했습니다."
            ),
        )


__all__ = ["CafeAgent"]
