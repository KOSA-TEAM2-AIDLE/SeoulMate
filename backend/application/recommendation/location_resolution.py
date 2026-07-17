from __future__ import annotations

from dataclasses import dataclass, field

from schemas.location import ResolvedPlace
from services.kakao_local import KakaoLocalServiceError
from services.place_resolver import PlaceResolver


# 프론트가 전달한 좌표가 있을 때만 사용자 현재 위치로 판단한다.
# Kakao에 지오코딩하면 '현재'라는 상호명이 반환될 수 있다.
CURRENT_LOCATION_ALIASES = frozenset({
    "현재 위치",
    "내 위치",
    "내 주변",
    "내 근처",
    "여기",
    "current location",
    "my location",
    "near me",
    "around here",
})


@dataclass(frozen=True)
class ResolvedSearchLocation:
    location_name: str | None
    latitude: float | None = None
    longitude: float | None = None
    source: str | None = None
    candidates: list[ResolvedPlace] = field(default_factory=list)
    requires_disambiguation: bool = False
    warning: str | None = None


class SearchLocationResolver:
    def __init__(self, resolver: PlaceResolver | None = None) -> None:
        self._resolver = resolver or PlaceResolver()

    async def resolve(
        self,
        *,
        location: str | None,
        latitude: float | None = None,
        longitude: float | None = None,
        current_location_name: str | None = None,
    ) -> ResolvedSearchLocation:
        if (latitude is None) != (longitude is None):
            raise ValueError("latitude와 longitude는 함께 입력해야 합니다.")

        target = (location or "").strip() or None
        current_location_alias = bool(
            target
            and target.casefold() in CURRENT_LOCATION_ALIASES
            and latitude is not None
            and longitude is not None
        )
        same_as_current = bool(
            target and current_location_name
            and target.casefold() == current_location_name.strip().casefold()
        )
        broad_seoul = target is not None and target.casefold() in {
            "서울", "서울시", "서울특별시", "seoul",
        }
        if target is None or current_location_alias or same_as_current or broad_seoul:
            return ResolvedSearchLocation(
                location_name=(
                    current_location_name
                    if current_location_alias
                    else target or current_location_name
                ),
                latitude=latitude,
                longitude=longitude,
                source="current_location" if latitude is not None else None,
            )

        try:
            # 시설명 정확 매칭은 사용자와의 거리보다 우선한다.
            # Kakao에 중심 좌표를 주면 거리순으로 입점 상점이
            # 원본 시설보다 앞서 정확히 같은 이름을 놓칠 수 있다.
            resolution = await self._resolver.resolve(query=target)
        except KakaoLocalServiceError as error:
            return ResolvedSearchLocation(location_name=target, warning=str(error))

        if resolution.selected is not None:
            selected = resolution.selected
            return ResolvedSearchLocation(
                location_name=selected.place_name,
                latitude=selected.latitude,
                longitude=selected.longitude,
                source=selected.source,
                candidates=resolution.candidates,
            )
        if latitude is not None and longitude is not None:
            try:
                centered = await self._resolver.resolve(
                    query=target,
                    center_latitude=latitude,
                    center_longitude=longitude,
                )
            except KakaoLocalServiceError:
                centered = None
            if centered is not None and centered.selected is not None:
                selected = centered.selected
                return ResolvedSearchLocation(
                    location_name=selected.place_name,
                    latitude=selected.latitude,
                    longitude=selected.longitude,
                    source=selected.source,
                    candidates=centered.candidates,
                )
        return ResolvedSearchLocation(
            location_name=target,
            candidates=resolution.candidates[:3],
            requires_disambiguation=resolution.requires_disambiguation,
            warning=None if resolution.candidates else f"서울에서 장소를 찾을 수 없습니다: {target}",
        )


__all__ = ["ResolvedSearchLocation", "SearchLocationResolver"]
