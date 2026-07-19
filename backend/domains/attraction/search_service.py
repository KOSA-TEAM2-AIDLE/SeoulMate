"""Structured 관광 요청을 장소·리뷰 Vector 검색 후보로 변환한다."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
import re

from domains.attraction.mapper import to_search_candidate
from domains.attraction.repository import AttractionRepository
from domains.attraction.reranker import AttractionReranker
from domains.attraction.search_plan import build_attraction_search_plan
from domains.common.models import DomainSearchRequest, SearchCandidate
from integrations.kakao.geocoding_client import geocode_kakao


GENERIC_TERMS = (
    "관광지", "명소", "추천", "갈만한", "가볼만한", "근처", "주변", "인근",
    "tourist attraction", "attraction", "recommend", "near", "nearby",
)
CURRENT_LOCATION_ALIASES = frozenset({
    "현재 위치",
    "내 위치",
    "내 주변",
    "여기",
    "current location",
    "my location",
    "near me",
})


def should_geocode_location(request: DomainSearchRequest) -> bool:
    """현재 위치 별칭은 시설명으로 지오코딩하지 않는다."""

    if not request.location:
        return False
    target = request.location.strip().casefold()
    if target in CURRENT_LOCATION_ALIASES:
        return False
    if (
        request.current_location_name
        and target == request.current_location_name.strip().casefold()
    ):
        # 이름만 같고 좌표가 없으면 거리 필터를 적용할 기준점이 없다.
        # 이 경우에는 명시된 관광 지역을 지오코딩해야 서울 전체 검색으로
        # 넓어지는 것을 막을 수 있다.
        return request.latitude is None or request.longitude is None
    return True


def build_attraction_semantic_query(request: DomainSearchRequest) -> str:
    query = request.search_query.strip()
    if request.location:
        query = re.sub(re.escape(request.location), " ", query, flags=re.IGNORECASE)
    for term in sorted(GENERIC_TERMS, key=len, reverse=True):
        query = re.sub(re.escape(term), " ", query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip(" ,.!?-/")
    themes = " ".join(
        theme.strip() for theme in request.themes
        if theme.strip() and theme.casefold() not in query.casefold()
    )
    semantic = " ".join(part for part in (query, themes) if part).strip()
    return semantic or "서울 관광"


class AttractionSearchService:
    domain = "attraction"
    implemented = True

    def __init__(self, *, repository: AttractionRepository | None = None, reranker: AttractionReranker | None = None, geocoder: Callable[[str], tuple[float, float, str] | None] = geocode_kakao) -> None:
        self.repository = repository or AttractionRepository()
        self.reranker = reranker or AttractionReranker()
        self.geocoder = geocoder

    def _search_sync(self, request: DomainSearchRequest) -> list[SearchCandidate]:
        if request.domain != self.domain:
            raise ValueError(f"AttractionSearchService에 {request.domain} 요청을 전달했습니다.")
        latitude = request.latitude
        longitude = request.longitude
        resolved_location = request.location
        if should_geocode_location(request):
            geocoded = self.geocoder(request.location)
            if geocoded:
                latitude, longitude, resolved_location = geocoded
            elif request.radius_km is not None:
                raise ValueError("관광 검색 반경을 적용할 목적지 좌표를 확인하지 못했습니다.")
        effective_request = request.model_copy(update={
            "latitude": latitude,
            "longitude": longitude,
        })
        as_of = request.visit_date or date.today()
        semantic_query = build_attraction_semantic_query(effective_request)
        retrieval = self.repository.retrieve(semantic_query, language=request.language, as_of=as_of)
        ranked = self.reranker.rerank(
            retrieval,
            plan=build_attraction_search_plan(effective_request),
            required_features=request.required_features,
            excluded_features=request.excluded_features,
            min_rating=request.min_rating,
            as_of=as_of,
            limit=request.candidate_count,
            search_location=resolved_location,
        )
        supporting = self.repository.fetch_supporting_reviews(
            retrieval.query_vector,
            [item.attraction.id for item in ranked],
            language=retrieval.language,
        )
        parsed_query = request.context.get("parsed_query")
        original_question = (
            getattr(parsed_query, "original_question", None)
            or (parsed_query.get("original_question") if isinstance(parsed_query, dict) else None)
            or request.search_query
        )
        return [
            to_search_candidate(
                item,
                request.task_id,
                supporting_reviews=supporting.get(item.attraction.id),
                original_question=original_question,
                required_features=request.required_features,
                excluded_features=request.excluded_features,
            )
            for item in ranked
        ]

    async def search(self, request: DomainSearchRequest) -> list[SearchCandidate]:
        return await asyncio.to_thread(self._search_sync, request)


__all__ = [
    "AttractionSearchService",
    "build_attraction_semantic_query",
    "should_geocode_location",
]
