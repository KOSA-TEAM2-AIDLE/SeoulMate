from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Any, Callable

from domains.common.models import DomainSearchRequest
from domains.attraction.search_plan import build_attraction_search_plan
from domains.attraction.taxonomy import normalize_metadata_category
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
    DEFAULT_RADIUS_KM = 5.0
    REVIEW_LIMIT_PER_PLACE = 5

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
        plan = build_attraction_search_plan(request)
        query = self.build_query_text(request)
        vectors = self._embedder([query])
        if len(vectors) != 1:
            raise RuntimeError("검색어 임베딩 결과는 정확히 하나여야 합니다.")

        as_of = request.visit_date or date.today()
        profiles = self._repository.search_profiles(
            vectors[0],
            language=request.language,
            as_of=as_of,
            limit=request.candidate_count * 10,
        )
        selected = []
        for row in profiles:
            if not self._matches_plan(row["metadata"], plan) or not self._is_active(row["metadata"], as_of):
                continue
            metadata = row["metadata"] = dict(row["metadata"])
            if plan.latitude is not None and plan.longitude is not None:
                distance_km = self._distance_km(metadata, plan.latitude, plan.longitude)
                if distance_km is None or distance_km > (plan.radius_km or self.DEFAULT_RADIUS_KM):
                    continue
                metadata["distance_km"] = round(distance_km, 3)
            selected.append(row)
        for row in selected:
            metadata = row["metadata"]
            metadata["category_match"] = bool(plan.primary_categories or plan.secondary_categories)
        selected = selected[:request.candidate_count]
        place_keys = [row["metadata"]["place_key"] for row in selected]
        reviews = self._repository.search_reviews(
            vectors[0],
            language=request.language,
            place_keys=place_keys,
            limit_per_place=self.REVIEW_LIMIT_PER_PLACE,
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

    @staticmethod
    def _matches_plan(metadata: dict[str, Any], plan) -> bool:
        if plan.event_only and metadata.get("kind") != "event":
            return False
        if not plan.primary_categories and not plan.secondary_categories:
            return True
        primary = metadata.get("category_primary")
        secondary = metadata.get("category_secondary")
        if not primary and not secondary:
            primary, secondary = normalize_metadata_category(str(metadata.get("category") or ""))
        if plan.secondary_categories:
            return secondary in plan.secondary_categories
        return primary in plan.primary_categories

    @staticmethod
    def _distance_km(metadata: dict[str, Any], latitude: float, longitude: float) -> float | None:
        try:
            target_latitude = float(metadata["latitude"])
            target_longitude = float(metadata["longitude"])
        except (KeyError, TypeError, ValueError):
            return None
        lat1, lat2 = math.radians(latitude), math.radians(target_latitude)
        delta_lat = math.radians(target_latitude - latitude)
        delta_lng = math.radians(target_longitude - longitude)
        value = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
        )
        return 6371.0088 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
