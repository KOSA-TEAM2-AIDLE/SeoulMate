"""Weather MCP의 사실을 식당 데이터와 조합하는 도메인별 재랭킹."""

from domains.common.models import SearchCandidate
from domains.restaurant.mapper import to_legacy_candidate, to_search_candidate
from services.weather_reranker import prepare_rag_only_candidates, rerank_with_weather


class RestaurantWeatherReranker:
    domain = "restaurant"
    implemented = True

    def rerank(
        self,
        candidates: list[SearchCandidate],
        weather: dict,
        query: str,
    ) -> list[SearchCandidate]:
        if not candidates:
            return []
        raw = [to_legacy_candidate(candidate) for candidate in candidates]
        reranked = rerank_with_weather(raw, weather, query, source_mode="rag_mcp")
        task_id = candidates[0].task_id
        return [to_search_candidate(item, task_id) for item in reranked]


__all__ = [
    "RestaurantWeatherReranker",
    "prepare_rag_only_candidates",
    "rerank_with_weather",
]
