"""검색부터 Context 보강·DSPy 선택까지 순서를 고정한다."""

from __future__ import annotations

from dataclasses import dataclass

from application.recommendation.selection_models import CandidateSelectionResult
from domains.attraction.context_enricher import AttractionContextEnricher
from domains.attraction.search_service import AttractionSearchService
from domains.attraction.selection_service import AttractionSelectionService
from domains.common.models import DomainSearchRequest, SearchCandidate


@dataclass(frozen=True)
class AttractionRecommendationResult:
    answer: CandidateSelectionResult
    candidates: list[SearchCandidate]


class AttractionRecommendationPipeline:
    """카페형 SearchService 뒤에 관광 전용 확장 단계만 조합한다."""

    def __init__(
        self,
        *,
        search_service=None,
        context_enricher=None,
        answer_generator=None,
        selection_service=None,
        congestion_reranker=None,
        weather_provider=None,
        weather_reranker=None,
    ) -> None:
        self._search_service = search_service or AttractionSearchService()
        self._context_enricher = context_enricher or AttractionContextEnricher(
            congestion_reranker=congestion_reranker,
            weather_provider=weather_provider,
            weather_reranker=weather_reranker,
        )
        if selection_service is not None and answer_generator is not None:
            raise ValueError(
                "selection_service와 answer_generator는 동시에 지정할 수 없습니다."
            )
        self._selection_service = selection_service or AttractionSelectionService(
            answer_generator=answer_generator,
        )

    async def recommend(
        self,
        request: DomainSearchRequest,
    ) -> AttractionRecommendationResult:
        if request.domain != "attraction":
            raise ValueError(f"관광 도메인 요청이 아닙니다: {request.domain}")
        candidates = await self._search_service.search(request)
        candidates = sorted(
            candidates,
            key=lambda candidate: candidate.final_score,
            reverse=True,
        )[:10]
        candidates = await self._context_enricher.enrich(request, candidates)
        answer = await self._selection_service.select(request, candidates)
        candidates_by_id = {
            candidate.place_id: candidate for candidate in candidates
        }
        selected_candidates = [
            candidates_by_id[selection.place_id]
            for selection in answer.selections
            if selection.place_id in candidates_by_id
        ]
        return AttractionRecommendationResult(
            answer=answer,
            candidates=selected_candidates,
        )


__all__ = [
    "AttractionRecommendationPipeline",
    "AttractionRecommendationResult",
]
