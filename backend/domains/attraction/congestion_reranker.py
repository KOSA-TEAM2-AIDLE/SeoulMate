from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from domains.common.models import SearchCandidate
from integrations.mcp.base_client import ContextProvider, ContextRequest


class AttractionCongestionReranker:
    MAX_CANDIDATES = 10
    MAX_CONCURRENCY = 4
    TIMEOUT_SECONDS = 15
    MAX_AGE_MINUTES = 180
    GENERAL_WEIGHT = 0.02
    EXPLICIT_WEIGHT = 0.10
    LOW_CONGESTION_TERMS = ("한적", "덜 붐", "붐비지", "혼잡하지", "low congestion", "less crowded", "quiet")

    def __init__(self, provider: ContextProvider) -> None:
        self._provider = provider

    async def rerank(
        self,
        candidates: list[SearchCandidate],
        question: str,
        *,
        language: str = "ko",
    ) -> list[SearchCandidate]:
        selected = candidates[: self.MAX_CANDIDATES]
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENCY)

        async def enrich(candidate: SearchCandidate) -> SearchCandidate:
            if candidate.latitude is None or candidate.longitude is None:
                return self._with_context(candidate, available=False, error="missing_coordinates")
            try:
                async with semaphore:
                    result = await asyncio.wait_for(
                        self._provider.get_context(ContextRequest(
                            query=question,
                            latitude=candidate.latitude,
                            longitude=candidate.longitude,
                            language=language,
                            place_name=candidate.name,
                        )),
                        timeout=self.TIMEOUT_SECONDS,
                    )
            except Exception as error:
                return self._with_context(candidate, available=False, error=f"{type(error).__name__}: {error}")
            if not result.available:
                return self._with_context(candidate, available=False, error=result.error)
            return self._apply(candidate, result.data, question)

        enriched = await asyncio.gather(*(enrich(candidate) for candidate in selected))
        enriched.sort(key=lambda candidate: candidate.final_score, reverse=True)
        return [*enriched, *candidates[self.MAX_CANDIDATES :]]

    def _apply(self, candidate: SearchCandidate, payload: dict, question: str) -> SearchCandidate:
        congestion = payload.get("congestion") or {}
        score = congestion.get("congestion_score")
        observed_at = _parse_datetime(congestion.get("observed_at"))
        fresh = observed_at is not None and (
            datetime.now(timezone.utc) - observed_at
        ).total_seconds() <= self.MAX_AGE_MINUTES * 60
        adjustment = 0.0
        if fresh and score is not None:
            weight = self.EXPLICIT_WEIGHT if any(term in question.casefold() for term in self.LOW_CONGESTION_TERMS) else self.GENERAL_WEIGHT
            centered = max(-1.0, min(1.0, (50.0 - float(score)) / 50.0))
            adjustment = centered * weight
        signals = dict(candidate.signals)
        signals.update({
            "congestion_available": True,
            "congestion_level": congestion.get("congestion_level"),
            "congestion_score": score,
            "congestion_observed_at": congestion.get("observed_at"),
            "congestion_fresh": fresh,
            "congestion_adjustment": adjustment,
        })
        return candidate.model_copy(update={
            "final_score": candidate.final_score + adjustment,
            "signals": signals,
        })

    @staticmethod
    def _with_context(candidate: SearchCandidate, *, available: bool, error: str | None) -> SearchCandidate:
        signals = dict(candidate.signals)
        signals.update({
            "congestion_available": available,
            "congestion_adjustment": 0.0,
            "congestion_error": error,
        })
        return candidate.model_copy(update={"signals": signals})


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


__all__ = ["AttractionCongestionReranker"]
