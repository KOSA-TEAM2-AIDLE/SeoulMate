"""현재 운영 중인 PostgreSQL·OpenAI embedding·RRF 식당 검색 어댑터."""

from __future__ import annotations

import asyncio

from domains.common.models import DomainSearchRequest, SearchCandidate
from domains.restaurant.mapper import to_search_candidate
from services.rag import search_restaurants_structured


class RestaurantSearchService:
    domain = "restaurant"
    implemented = True

    async def search(self, request: DomainSearchRequest) -> list[SearchCandidate]:
        if request.domain != self.domain:
            raise ValueError(f"RestaurantSearchService에 {request.domain} 요청을 전달했습니다.")
        parsed_query = request.context.get("parsed_query")
        task = request.context.get("task")
        if parsed_query is None or task is None:
            raise ValueError(
                "식당 어댑터에는 context.parsed_query와 context.task가 필요합니다. "
                "Structured Query를 다시 자연어 파싱하지 마세요."
            )
        result = await asyncio.to_thread(
            search_restaurants_structured,
            parsed_query,
            task,
            current_lat=request.latitude,
            current_lng=request.longitude,
            current_location_name=request.current_location_name,
            top_n=request.candidate_count,
        )
        return [
            to_search_candidate(raw, request.task_id)
            for raw in (result.get("candidates") or [])
        ]


__all__ = ["RestaurantSearchService"]

