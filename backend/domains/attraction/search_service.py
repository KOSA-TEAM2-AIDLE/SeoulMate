from __future__ import annotations

import asyncio

from domains.attraction.repository import AttractionRepository
from domains.common.models import DomainSearchRequest, SearchCandidate
from vector_db.attraction.search import VectorSearchHit


class AttractionSearchService:
    domain = "attraction"
    implemented = True

    def __init__(self, *, repository: AttractionRepository | None = None) -> None:
        self._repository = repository or AttractionRepository()

    async def search(self, request: DomainSearchRequest) -> list[SearchCandidate]:
        if request.domain != self.domain:
            raise ValueError(f"AttractionSearchService에 {request.domain} 요청을 전달했습니다.")
        hits = await asyncio.to_thread(self._repository.search, request)
        return [
            self._to_candidate(hit, request)
            for hit in hits
            if hit.metadata.get("lang") == request.language
        ]

    @staticmethod
    def _to_candidate(hit: VectorSearchHit, request: DomainSearchRequest) -> SearchCandidate:
        metadata = hit.metadata
        return SearchCandidate(
            domain="attraction",
            place_id=hit.place_key,
            task_id=request.task_id,
            name=_content_value(hit.content, "Name") or hit.place_key,
            category=str(metadata.get("category") or _content_value(hit.content, "Category") or ""),
            latitude=metadata.get("latitude"),
            longitude=metadata.get("longitude"),
            base_score=hit.similarity,
            final_score=hit.similarity,
            evidence=[review.content for review in hit.reviews],
            attributes={
                "address": metadata.get("road_address") or _content_value(hit.content, "Address"),
                "kind": metadata.get("kind"),
                "start_date": metadata.get("start_date"),
                "end_date": metadata.get("end_date"),
                "homepage_url": metadata.get("homepage_url"),
                "language": metadata.get("lang"),
                "review_count": len(hit.reviews),
            },
            signals={"source_kind": "vector_db", "vector_similarity": hit.similarity},
        )


def _content_value(content: str, label: str) -> str | None:
    prefix = f"{label}: "
    for line in content.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip() or None
    return None


__all__ = ["AttractionSearchService"]
