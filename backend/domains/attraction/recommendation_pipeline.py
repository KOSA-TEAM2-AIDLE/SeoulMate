"""검색부터 DSPy 답변까지 연결하는 attraction 전용 경계."""

from __future__ import annotations

from dataclasses import dataclass

from application.recommendation.selection_models import CandidateSelectionResult
from domains.attraction.congestion_reranker import AttractionCongestionReranker
from domains.attraction.search_service import AttractionSearchService
from domains.attraction.selection_service import AttractionSelectionService
from domains.common.models import DomainSearchRequest, SearchCandidate
from integrations.mcp.congestion_client import CongestionMCPProvider


_DEFAULT_CONGESTION_RERANKER = object()


@dataclass(frozen=True)
class AttractionRecommendationResult:
    """DSPy 답변과 그 답변이 선택한 원본 후보."""

    answer: CandidateSelectionResult
    candidates: list[SearchCandidate]


class AttractionRecommendationPipeline:
    """검색 → 정적 재랭킹 → 혼잡도 → DSPy 순서를 고정한다."""

    def __init__(
        self,
        *,
        search_service=None,
        congestion_reranker=_DEFAULT_CONGESTION_RERANKER,
        answer_generator=None,
        selection_service=None,
    ) -> None:
        self._search_service = search_service or AttractionSearchService()
        self._congestion_reranker = (
            AttractionCongestionReranker(CongestionMCPProvider())
            if congestion_reranker is _DEFAULT_CONGESTION_RERANKER
            else congestion_reranker
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
        *,
        use_congestion: bool = False,
    ) -> AttractionRecommendationResult:
        if request.domain != "attraction":
            raise ValueError(f"관광 도메인 요청이 아닙니다: {request.domain}")
        candidates = await self._search_service.search(request)
        candidates = sorted(
            candidates,
            key=lambda candidate: candidate.final_score,
            reverse=True,
        )[:10]
        if use_congestion and self._congestion_reranker is not None:
            candidates = await self._congestion_reranker.rerank(
                candidates,
                request.search_query,
                language=request.language,
            )
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
