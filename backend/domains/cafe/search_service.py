"""Structured 카페 요청을 벡터 검색·RRF 후보로 변환한다."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable

from domains.cafe.mapper import to_search_candidate
from domains.cafe.repository import CafeRepository
from domains.cafe.reranker import CafeReranker
from domains.common.models import DomainSearchRequest, SearchCandidate
from integrations.kakao.geocoding_client import geocode_kakao


DEFAULT_LOCATION_RADIUS_KM = 2.0
FALLBACK_LOCATION_RADIUS_KM = 5.0
LOCATION_CAFE_VECTOR_LIMIT = 500
LOCATION_REVIEW_VECTOR_POOL = 500
CURRENT_LOCATION_ALIASES = frozenset({
    "현재 위치",
    "내 위치",
    "여기",
    "current location",
    "my location",
    "near me",
})
GENERIC_CAFE_TERMS = (
    "coffee shop",
    "coffee shops",
    "cafes",
    "cafe",
    "카페",
    "커피숍",
    "커피샵",
)
CATEGORY_TERMS = (
    ("베이커리", "베이커리"),
    ("빵집", "베이커리"),
    ("bakery", "Bakery"),
    ("디저트", "디저트"),
    ("dessert", "Dessert"),
    ("브런치", "브런치"),
    ("brunch", "Brunch"),
    ("티하우스", "차"),
    ("찻집", "차"),
    ("tea house", "Tea"),
)


def build_cafe_semantic_query(request: DomainSearchRequest) -> str:
    """위치와 일반 도메인명은 제거하고 카페 선택 의미만 임베딩한다."""

    query = request.search_query.strip()
    if request.location:
        query = re.sub(
            re.escape(request.location),
            " ",
            query,
            flags=re.IGNORECASE,
        )
    for term in sorted(GENERIC_CAFE_TERMS, key=len, reverse=True):
        query = re.sub(
            rf"\b{re.escape(term)}\b" if term.isascii() else re.escape(term),
            " ",
            query,
            flags=re.IGNORECASE,
        )
    query = re.sub(r"\s+", " ", query).strip(" ,.!?-/")
    theme_text = " ".join(
        theme.strip()
        for theme in request.themes
        if theme.strip() and theme.strip().casefold() not in query.casefold()
    )
    semantic = " ".join(part for part in (query, theme_text) if part).strip()
    return semantic or request.search_query.strip()


def extract_cafe_category_hint(request: DomainSearchRequest) -> str | None:
    text = " ".join(
        [request.search_query, *request.themes]
    ).casefold()
    for term, category in CATEGORY_TERMS:
        if term.casefold() in text:
            return category
    return None


def _same_location(target: str | None, current: str | None) -> bool:
    if not target or not current:
        return False
    return target.strip().casefold() == current.strip().casefold()


def _is_current_location(target: str | None) -> bool:
    if not target:
        return False
    return target.strip().casefold() in CURRENT_LOCATION_ALIASES


class CafeSearchService:
    domain = "cafe"
    implemented = True

    def __init__(
        self,
        repository: CafeRepository | None = None,
        reranker: CafeReranker | None = None,
        *,
        geocoder: Callable[[str], tuple[float, float, str] | None] = geocode_kakao,
    ) -> None:
        self.repository = repository or CafeRepository()
        self.reranker = reranker or CafeReranker()
        self.geocoder = geocoder

    def _search_sync(
        self,
        request: DomainSearchRequest,
    ) -> list[SearchCandidate]:
        if request.domain != self.domain:
            raise ValueError(
                f"CafeSearchService에 {request.domain} 요청이 전달되었습니다."
            )

        origin_latitude = request.latitude
        origin_longitude = request.longitude
        target_location = request.location
        if (
            target_location
            and not _is_current_location(target_location)
            and not _same_location(target_location, request.current_location_name)
        ):
            geocoded = self.geocoder(target_location)
            if geocoded:
                origin_latitude, origin_longitude, _ = geocoded
            else:
                origin_latitude, origin_longitude = None, None

        radius_km = request.radius_km
        has_origin = origin_latitude is not None and origin_longitude is not None
        uses_default_radius = radius_km is None and bool(target_location) and has_origin
        if radius_km is None and target_location and has_origin:
            radius_km = DEFAULT_LOCATION_RADIUS_KM
        if request.radius_km is not None and not has_origin:
            raise ValueError(
                "요청한 카페 검색 반경을 적용할 목적지 좌표를 확인하지 못했습니다."
            )

        semantic_query = build_cafe_semantic_query(request)
        retrieval_options = {}
        if has_origin and radius_km is not None:
            retrieval_options = {
                "cafe_limit": LOCATION_CAFE_VECTOR_LIMIT,
                "review_pool": LOCATION_REVIEW_VECTOR_POOL,
            }
        retrieval = self.repository.retrieve(
            semantic_query,
            language=request.language,
            **retrieval_options,
        )
        ranked = self.reranker.rerank(
            retrieval,
            category_hint=extract_cafe_category_hint(request),
            min_rating=request.min_rating,
            origin_latitude=origin_latitude,
            origin_longitude=origin_longitude,
            radius_km=radius_km,
            limit=request.candidate_count,
        )
        if not ranked and uses_default_radius:
            ranked = self.reranker.rerank(
                retrieval,
                category_hint=extract_cafe_category_hint(request),
                min_rating=request.min_rating,
                origin_latitude=origin_latitude,
                origin_longitude=origin_longitude,
                radius_km=FALLBACK_LOCATION_RADIUS_KM,
                limit=request.candidate_count,
            )
        supporting_reviews = self.repository.fetch_supporting_reviews(
            retrieval.query_vector,
            [candidate.cafe.id for candidate in ranked],
            language=retrieval.language,
        )
        return [
            to_search_candidate(
                candidate,
                request.task_id,
                supporting_reviews=supporting_reviews.get(candidate.cafe.id),
            )
            for candidate in ranked
        ]

    async def search(
        self,
        request: DomainSearchRequest,
    ) -> list[SearchCandidate]:
        return await asyncio.to_thread(self._search_sync, request)


__all__ = [
    "CafeSearchService",
    "build_cafe_semantic_query",
    "extract_cafe_category_hint",
]
