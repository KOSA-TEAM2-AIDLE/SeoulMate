"""Structured Task → Registry 검색 → 선택적 MCP → 도메인 재랭킹."""

from __future__ import annotations

from pydantic import BaseModel, Field

from application.recommendation.request_factory import build_domain_search_request
from application.tool_policy import requested_contexts
from domains.common.models import SearchCandidate
from domains.common.registry import DomainSearchRegistry, build_default_domain_registry
from domains.restaurant.weather_policy import RestaurantWeatherReranker
from domains.attraction.congestion_reranker import AttractionCongestionReranker
from integrations.kakao.geocoding_client import geocode_kakao
from integrations.mcp.base_client import ContextRequest
from integrations.mcp.registry import ContextProviderRegistry, build_default_context_registry
from schemas.structured_query import StructuredTravelQuery
from services.query_policy import derive_source_mode, effective_task_filters


class TaskExecutionResult(BaseModel):
    task_id: str
    domain: str
    source_mode: str
    candidates: list[SearchCandidate]
    contexts: dict[str, dict] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class RecommendationOrchestrator:
    def __init__(
        self,
        domain_registry: DomainSearchRegistry | None = None,
        context_registry: ContextProviderRegistry | None = None,
    ) -> None:
        self.domains = domain_registry or build_default_domain_registry()
        self.contexts = context_registry or build_default_context_registry()
        self.restaurant_weather = RestaurantWeatherReranker()
        self.attraction_congestion = AttractionCongestionReranker(
            self.contexts.get("congestion")
        )

    async def execute(
        self,
        parsed: StructuredTravelQuery,
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        current_location_name: str | None = None,
        candidate_count: int = 10,
    ) -> list[TaskExecutionResult]:
        mode = derive_source_mode(parsed)
        results: list[TaskExecutionResult] = []
        for task in parsed.tasks:
            request = build_domain_search_request(
                parsed,
                task,
                latitude=latitude,
                longitude=longitude,
                current_location_name=current_location_name,
                candidate_count=candidate_count,
            )
            candidates = await self.domains.get(task.domain).search(request)
            context_data: dict[str, dict] = {}
            warnings: list[str] = []
            for context_name in requested_contexts(mode, task.domain):
                task_filters = effective_task_filters(parsed, task)
                target_lat, target_lng = latitude, longitude
                target_name = task_filters.location or current_location_name
                if target_name and target_name != current_location_name:
                    geocoded = geocode_kakao(target_name)
                    if geocoded:
                        target_lat, target_lng, target_name = geocoded
                if target_lat is None or target_lng is None:
                    warnings.append(f"{context_name}: 좌표가 없어 호출하지 않았습니다.")
                    continue
                provider = self.contexts.get(context_name)
                context = await provider.get_context(ContextRequest(
                    query=parsed.original_question,
                    latitude=target_lat,
                    longitude=target_lng,
                    language=parsed.language,
                    place_name=target_name,
                    target_date=(request.visit_date.isoformat() if request.visit_date else None),
                    target_time=request.start_time,
                ))
                context_data[context_name] = context.data
                if not context.available:
                    warnings.append(f"{context_name}: {context.error or '사용 불가'}")
            if task.domain == "restaurant" and "weather" in context_data:
                candidates = self.restaurant_weather.rerank(
                    candidates,
                    context_data["weather"],
                    parsed.original_question,
                )
            if task.domain == "attraction" and mode == "rag_mcp":
                candidates = await self.attraction_congestion.rerank(
                    candidates,
                    parsed.original_question,
                    language=parsed.language,
                )
            results.append(TaskExecutionResult(
                task_id=task.task_id,
                domain=task.domain,
                source_mode=mode,
                candidates=candidates,
                contexts=context_data,
                warnings=warnings,
            ))
        return results


__all__ = ["RecommendationOrchestrator", "TaskExecutionResult"]
