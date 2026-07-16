from __future__ import annotations

from dataclasses import dataclass, field

from schemas.location import ResolvedPlace
from services.kakao_local import KakaoLocalServiceError
from services.place_resolver import PlaceResolver


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
        same_as_current = bool(
            target and current_location_name
            and target.casefold() == current_location_name.strip().casefold()
        )
        broad_seoul = target is not None and target.casefold() in {
            "서울", "서울시", "서울특별시", "seoul",
        }
        if target is None or same_as_current or broad_seoul:
            return ResolvedSearchLocation(
                location_name=target or current_location_name,
                latitude=latitude,
                longitude=longitude,
                source="current_location" if latitude is not None else None,
            )

        try:
            resolution = await self._resolver.resolve(
                query=target,
                center_latitude=latitude,
                center_longitude=longitude,
            )
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
        return ResolvedSearchLocation(
            location_name=target,
            candidates=resolution.candidates[:3],
            requires_disambiguation=resolution.requires_disambiguation,
            warning=None if resolution.candidates else f"서울에서 장소를 찾을 수 없습니다: {target}",
        )


__all__ = ["ResolvedSearchLocation", "SearchLocationResolver"]
