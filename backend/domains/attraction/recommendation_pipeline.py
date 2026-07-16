"""검색부터 DSPy 답변까지 연결하는 attraction 전용 경계."""

from __future__ import annotations

from domains.attraction.answer_generator import AttractionAnswerGenerator
from domains.attraction.search_service import AttractionSearchService
from domains.common.models import DomainSearchRequest


class AttractionRecommendationPipeline:
    """검색 → 정적 재랭킹 → 혼잡도 → DSPy 순서를 고정한다."""

    def __init__(
        self,
        *,
        search_service=None,
        congestion_reranker=None,
        answer_generator=None,
    ) -> None:
        self._search_service = search_service or AttractionSearchService()
        self._congestion_reranker = congestion_reranker
        self._answer_generator = answer_generator or AttractionAnswerGenerator()

    async def recommend(self, request: DomainSearchRequest):
        if request.domain != "attraction":
            raise ValueError(f"관광 도메인 요청이 아닙니다: {request.domain}")
        candidates = await self._search_service.search(request)
        candidates = sorted(
            candidates,
            key=lambda candidate: candidate.final_score,
            reverse=True,
        )[:10]
        if self._congestion_reranker is not None:
            candidates = await self._congestion_reranker.rerank(
                candidates,
                request.search_query,
                language=request.language,
            )
        return await self._answer_generator.generate(
            question=request.search_query,
            language=request.language,
            location=request.location or request.current_location_name,
            themes=request.themes,
            candidates=candidates,
        )


__all__ = ["AttractionRecommendationPipeline"]
