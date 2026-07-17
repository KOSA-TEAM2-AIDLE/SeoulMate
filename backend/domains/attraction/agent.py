"""Structured Query를 관광 검색과 DSPy 답변으로 연결한다."""

from application.recommendation.request_factory import build_domain_search_request
from application.recommendation.location_resolution import SearchLocationResolver
from core.config import settings
from domains.attraction.congestion_reranker import AttractionCongestionReranker
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

    CURRENT_LOCATION_NAMES = {
        "현재 위치", "내 위치", "내 주변", "내 근처",
        "current location", "near me", "nearby me", "around me",
    }
    CURRENT_LOCATION_TERMS = (
        "내 주변", "내 근처", "내 위치", "현재 위치",
        "near me", "nearby me", "around me", "current location",
    )
    BROAD_LOCATIONS = {"서울", "서울시", "서울특별시", "seoul"}

    def __init__(self, *, pipeline=None, location_resolver=None) -> None:
        self._pipeline = pipeline or AttractionRecommendationPipeline()
        self._location_resolver = location_resolver or SearchLocationResolver()

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
            filters = task.filters or query.filters
            location = (filters.location or query.filters.location or "").strip()
            latitude, longitude, location_name = await self._resolve_location(
                location=location,
                response=response,
                use_current_location=self._uses_current_location(
                    query.original_question
                ),
            )
            request = build_domain_search_request(
                query,
                task,
                latitude=latitude,
                longitude=longitude,
                current_location_name=location_name,
            )
            use_congestion = (
                latitude is not None
                or AttractionCongestionReranker.prefers_low_congestion(
                    query.original_question
                )
            )
            results.append(await self._pipeline.recommend(
                request,
                use_congestion=use_congestion,
            ))
        return DomainAgentDispatchResult(
            domain=self.domain,
            task_ids=[task.task_id for task in tasks],
            candidates=[
                candidate
                for result in results
                for candidate in result.candidates
            ][:settings.attraction_recommendation_limit],
            assistant_message="\n\n".join(
                result.answer.answer for result in results
            ),
        )

    async def _resolve_location(
        self,
        *,
        location: str,
        response: TravelQueryApiResponse,
        use_current_location: bool,
    ) -> tuple[float | None, float | None, str | None]:
        context = response.execution_context
        normalized = location.casefold()
        if use_current_location or normalized in self.CURRENT_LOCATION_NAMES:
            return context.latitude, context.longitude, (
                context.location_name or location or None
            )
        if not location or normalized in self.BROAD_LOCATIONS:
            return None, None, location or None

        resolved = await self._location_resolver.resolve(
            location=location,
            latitude=context.latitude,
            longitude=context.longitude,
            current_location_name=context.location_name,
        )
        return (
            resolved.latitude,
            resolved.longitude,
            resolved.location_name or location,
        )

    @classmethod
    def _uses_current_location(cls, question: str) -> bool:
        normalized = question.casefold()
        return any(term in normalized for term in cls.CURRENT_LOCATION_TERMS)


__all__ = ["AttractionAgent"]
