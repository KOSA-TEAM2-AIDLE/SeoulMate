"""Structured Query를 관광 검색과 DSPy 답변으로 연결한다."""

from application.recommendation.request_factory import build_domain_search_request
from domains.attraction.recommendation_pipeline import (
    AttractionRecommendationPipeline,
)
from schemas.travel_query_api import (
    DomainAgentDispatchResult,
    TravelQueryApiResponse,
)


class AttractionAgent:
    """관광 Task만 선택해 관광 추천 파이프라인으로 전달한다."""

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
        results = [
            await self._pipeline.recommend(
                build_domain_search_request(query, task)
            )
            for task in tasks
        ]
        return DomainAgentDispatchResult(
            domain=self.domain,
            task_ids=[task.task_id for task in tasks],
            assistant_message="\n\n".join(result.answer for result in results),
        )


__all__ = ["AttractionAgent"]
