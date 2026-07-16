from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from domains.common.models import DomainSearchRequest
from vector_db.attraction.embedder import embed_texts
from vector_db.attraction.repository import AttractionVectorRepository


@dataclass(frozen=True)
class ReviewEvidence:
    document_id: str
    content: str
    metadata: dict[str, Any]
    similarity: float


@dataclass(frozen=True)
class VectorSearchHit:
    document_id: str
    place_key: str
    content: str
    metadata: dict[str, Any]
    similarity: float
    reviews: list[ReviewEvidence]


class AttractionVectorSearch:
    def __init__(
        self,
        *,
        repository: AttractionVectorRepository | None = None,
        embedder: Callable[[list[str]], list[list[float]]] = embed_texts,
    ) -> None:
        self._repository = repository or AttractionVectorRepository()
        self._embedder = embedder

    @staticmethod
    def build_query_text(request: DomainSearchRequest) -> str:
        parts = [request.search_query]
        if request.themes:
            parts.append(f"테마: {', '.join(request.themes)}")
        if request.location:
            parts.append(f"위치: {request.location}")
        if request.visit_date:
            parts.append(f"방문일: {request.visit_date.isoformat()}")
        if request.required_features:
            parts.append(f"필수 조건: {', '.join(request.required_features)}")
        if request.excluded_features:
            parts.append(f"제외 조건: {', '.join(request.excluded_features)}")
        return " | ".join(parts)

    def search(self, request: DomainSearchRequest) -> list[VectorSearchHit]:
        query = self.build_query_text(request)
        vectors = self._embedder([query])
        if len(vectors) != 1:
            raise RuntimeError("검색어 임베딩 결과는 정확히 하나여야 합니다.")

        as_of = request.visit_date or date.today()
        profiles = self._repository.search_profiles(
            vectors[0],
            language=request.language,
            as_of=as_of,
            limit=request.candidate_count * 3,
        )
        selected = [row for row in profiles if self._is_active(row["metadata"], as_of)][:request.candidate_count]
        place_keys = [row["metadata"]["place_key"] for row in selected]
        reviews = self._repository.search_reviews(
            vectors[0],
            language=request.language,
            place_keys=place_keys,
            limit_per_place=3,
        )
        reviews_by_place: dict[str, list[ReviewEvidence]] = {place_key: [] for place_key in place_keys}
        for row in reviews:
            place_key = row["metadata"].get("place_key")
            if place_key in reviews_by_place:
                reviews_by_place[place_key].append(
                    ReviewEvidence(
                        document_id=row["document_id"],
                        content=row["content"],
                        metadata=row["metadata"],
                        similarity=1 - row["distance"],
                    )
                )

        return [
            VectorSearchHit(
                document_id=row["document_id"],
                place_key=row["metadata"]["place_key"],
                content=row["content"],
                metadata=row["metadata"],
                similarity=1 - row["distance"],
                reviews=reviews_by_place[row["metadata"]["place_key"]],
            )
            for row in selected
        ]

    @staticmethod
    def _is_active(metadata: dict[str, Any], as_of: date) -> bool:
        if metadata.get("kind") != "event":
            return True
        end_date = metadata.get("end_date", "")
        if not end_date:
            return True
        try:
            return date.fromisoformat(end_date) >= as_of
        except ValueError:
            return False
