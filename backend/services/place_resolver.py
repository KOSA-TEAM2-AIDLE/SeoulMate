import re

from schemas.location import (
    KakaoPlaceDocument,
    PlaceResolutionResult,
    ResolvedPlace,
)
from services.kakao_local import KakaoLocalClient


class PlaceResolver:
    """Kakao Local API 결과에서 서울 내 장소 후보를 선택한다."""

    def __init__(self, client: KakaoLocalClient | None = None) -> None:
        self._client = client or KakaoLocalClient()

    @staticmethod
    def _normalize_name(value: str) -> str:
        return re.sub(r"[^0-9a-z가-힣]+", "", value.casefold())

    @staticmethod
    def _is_in_seoul(document: KakaoPlaceDocument) -> bool:
        addresses = (document.road_address_name, document.address_name)
        return any(
            address is not None
            and address.lstrip().startswith(("서울 ", "서울특별시 "))
            for address in addresses
        )

    @classmethod
    def resolve_candidates(
        cls,
        query: str,
        documents: list[KakaoPlaceDocument],
    ) -> PlaceResolutionResult:
        normalized_query = cls._normalize_name(query)
        if not normalized_query:
            raise ValueError("검색할 장소명이 필요합니다.")

        seoul_documents = [
            document for document in documents if cls._is_in_seoul(document)
        ]
        exact_documents = [
            document
            for document in seoul_documents
            if cls._normalize_name(document.place_name) == normalized_query
        ]

        # 정확히 일치하는 원본 시설을 주차장·관리단·입점 시설보다 앞에 두는다.
        exact_ids = {document.id for document in exact_documents}
        ordered_documents = exact_documents + [
            document
            for document in seoul_documents
            if document.id not in exact_ids
        ]
        candidates = [
            document.to_resolved_place() for document in ordered_documents
        ]

        selected: ResolvedPlace | None = None
        requires_disambiguation = False

        if len(exact_documents) == 1:
            selected = candidates[0]
        elif len(exact_documents) > 1:
            requires_disambiguation = True
        elif len(candidates) == 1:
            selected = candidates[0]
        elif len(candidates) > 1:
            requires_disambiguation = True

        return PlaceResolutionResult(
            query=query,
            selected=selected,
            candidates=candidates,
            requires_disambiguation=requires_disambiguation,
        )

    async def resolve(
        self,
        query: str,
        center_latitude: float | None = None,
        center_longitude: float | None = None,
    ) -> PlaceResolutionResult:
        documents = await self._client.search_places(
            query=query,
            center_latitude=center_latitude,
            center_longitude=center_longitude,
        )
        return self.resolve_candidates(query, documents)
