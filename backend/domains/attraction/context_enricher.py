"""관광 후보에 혼잡도·날씨 Context를 선택적으로 보강한다."""

from __future__ import annotations

from domains.attraction.congestion_reranker import AttractionCongestionReranker
from domains.attraction.weather_reranker import AttractionWeatherReranker
from domains.common.models import DomainSearchRequest, SearchCandidate
from integrations.mcp.base_client import ContextRequest
from integrations.mcp.congestion_client import CongestionMCPProvider
from integrations.mcp.weather_client import WeatherMCPProvider


class AttractionContextEnricher:
    """MCP 호출 정책을 Agent와 SearchService 밖에 격리한다."""

    def __init__(
        self,
        *,
        congestion_reranker: AttractionCongestionReranker | None = None,
        weather_provider=None,
        weather_reranker: AttractionWeatherReranker | None = None,
    ) -> None:
        self._congestion = congestion_reranker or AttractionCongestionReranker(
            CongestionMCPProvider()
        )
        self._weather_provider = weather_provider or WeatherMCPProvider()
        self._weather = weather_reranker or AttractionWeatherReranker()

    async def enrich(
        self,
        request: DomainSearchRequest,
        candidates: list[SearchCandidate],
        *,
        include_congestion: bool = True,
    ) -> list[SearchCandidate]:
        if not candidates:
            return []
        question = _original_question(request)
        enriched = candidates

        if include_congestion and self._should_use_congestion(request, question):
            enriched = await self._congestion.rerank(
                enriched,
                question,
                language=request.language,
            )

        if self._weather.should_use_weather(
            question,
            has_visit_date=request.visit_date is not None,
        ):
            enriched = await self._enrich_weather(request, enriched, question)
        return enriched

    @staticmethod
    def _should_use_congestion(
        request: DomainSearchRequest,
        question: str,
    ) -> bool:
        return bool(
            request.location
            or (request.latitude is not None and request.longitude is not None)
            or AttractionCongestionReranker.prefers_low_congestion(question)
        )

    async def _enrich_weather(
        self,
        request: DomainSearchRequest,
        candidates: list[SearchCandidate],
        question: str,
    ) -> list[SearchCandidate]:
        latitude = request.latitude
        longitude = request.longitude
        if latitude is None or longitude is None:
            first_with_coordinates = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.latitude is not None
                    and candidate.longitude is not None
                ),
                None,
            )
            if first_with_coordinates is not None:
                latitude = first_with_coordinates.latitude
                longitude = first_with_coordinates.longitude
        if latitude is None or longitude is None:
            return self._weather.rerank(
                candidates,
                {"available": False, "error": "missing_coordinates"},
                question,
            )

        context = await self._weather_provider.get_context(ContextRequest(
            query=question,
            latitude=latitude,
            longitude=longitude,
            language=request.language,
            place_name=request.location or request.current_location_name,
            target_date=(request.visit_date.isoformat() if request.visit_date else None),
            target_time=request.start_time,
        ))
        payload = dict(context.data)
        payload.setdefault("available", context.available)
        payload.setdefault("error", context.error)
        return self._weather.rerank(candidates, payload, question)


def _original_question(request: DomainSearchRequest) -> str:
    parsed_query = request.context.get("parsed_query")
    return (
        getattr(parsed_query, "original_question", None)
        or (
            parsed_query.get("original_question")
            if isinstance(parsed_query, dict)
            else None
        )
        or request.search_query
    )


__all__ = ["AttractionContextEnricher"]
