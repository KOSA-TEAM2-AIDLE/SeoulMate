"""구조화된 관광 Task를 관광 추천 파이프라인으로 전달한다."""

from application.recommendation.request_factory import build_domain_search_request
from domains.attraction.recommendation_pipeline import (
    AttractionRecommendationPipeline,
)
from schemas.travel_query_api import (
    DomainAgentDispatchResult,
    TravelQueryApiResponse,
)


class AttractionAgent:
    """카페 Agent와 같은 형태의 얇은 도메인 어댑터."""

    domain = "attraction"

    def __init__(self, *, pipeline=None) -> None:
        self._pipeline = pipeline or AttractionRecommendationPipeline()

    async def execute(
        self,
        response: TravelQueryApiResponse,
    ) -> DomainAgentDispatchResult:
        if response.status != "ready":
            raise ValueError("ready 상태에서만 관광 에이전트를 실행할 수 있습니다.")
        query = response.structured_query
        if query is None:
            raise ValueError("structured_query가 없습니다.")

        tasks = [task for task in query.tasks if task.domain == self.domain]
        results = []
        for task in tasks:
            request = build_domain_search_request(
                query,
                task,
                latitude=response.current_latitude,
                longitude=response.current_longitude,
                current_location_name=response.current_location_name,
                candidate_count=max(10, task.desired_count),
            )
            results.append(await self._pipeline.recommend(request))

        candidates = [
            candidate
            for result in results
            for candidate in result.candidates
        ]
        return DomainAgentDispatchResult(
            domain=self.domain,
            status="completed",
            task_ids=[task.task_id for task in tasks],
            candidates=candidates,
            assistant_message="\n\n".join(
                result.answer.answer for result in results
            ),
        )


__all__ = ["AttractionAgent"]
