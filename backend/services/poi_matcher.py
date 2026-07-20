import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

from schemas.poi import PoiMatch


EARTH_RADIUS_METERS = 6_371_000


class PoiNotSupportedError(Exception):
    """좌표가 지원 가능한 POI 거리 밖에 있을 때 발생."""


class PoiDataError(Exception):
    """POI GeoJSON이 없거나 올바르지 않을 때 발생."""


@dataclass(frozen=True)
class _PoiArea:
    area_code: str
    area_name: str
    category: str
    geometry: BaseGeometry


def _distance_meters(first: Point, second: Point) -> float:
    lon1, lat1, lon2, lat2 = map(
        math.radians,
        (first.x, first.y, second.x, second.y),
    )
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(value))


class PoiMatcher:
    MAX_NEARBY_RESULTS = 10

    def __init__(
        self,
        geojson: dict[str, Any],
        max_distance_meters: float = 2_000,
    ) -> None:
        if max_distance_meters < 0:
            raise ValueError("최대 POI 거리는 0 이상이어야 합니다.")

        self._max_distance_meters = max_distance_meters
        self._areas = self._load_areas(geojson)

    @classmethod
    def from_file(
        cls,
        path: Path,
        max_distance_meters: float = 2_000,
    ) -> "PoiMatcher":
        try:
            geojson = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PoiDataError("POI GeoJSON을 읽을 수 없습니다.") from exc
        return cls(geojson, max_distance_meters=max_distance_meters)

    @staticmethod
    def _load_areas(geojson: dict[str, Any]) -> list[_PoiArea]:
        if geojson.get("type") != "FeatureCollection":
            raise PoiDataError("POI 데이터가 GeoJSON FeatureCollection이 아닙니다.")

        areas: list[_PoiArea] = []
        for feature in geojson.get("features", []):
            properties = feature.get("properties", {})
            try:
                geometry = shape(feature["geometry"])
                area = _PoiArea(
                    area_code=properties["area_code"],
                    area_name=properties["area_name"],
                    category=properties["category"],
                    geometry=geometry,
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise PoiDataError("POI Feature 구조가 올바르지 않습니다.") from exc

            if geometry.is_empty or not geometry.is_valid:
                raise PoiDataError(f"유효하지 않은 POI 도형입니다: {area.area_code}")
            areas.append(area)

        if not areas:
            raise PoiDataError("POI Feature가 없습니다.")
        return areas

    def match(self, latitude: float, longitude: float) -> PoiMatch:
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("위도 또는 경도의 범위가 올바르지 않습니다.")

        point = Point(longitude, latitude)
        containing_areas = [
            area for area in self._areas if area.geometry.covers(point)
        ]
        if containing_areas:
            most_specific = min(
                containing_areas,
                key=lambda area: area.geometry.area,
            )
            return self._to_match(most_specific, "contains", 0.0)

        nearest_area: _PoiArea | None = None
        nearest_distance = math.inf
        for area in self._areas:
            boundary_point = nearest_points(area.geometry, point)[0]
            distance = _distance_meters(point, boundary_point)
            if distance < nearest_distance:
                nearest_area = area
                nearest_distance = distance

        if nearest_area is None or nearest_distance > self._max_distance_meters:
            raise PoiNotSupportedError(
                "좌표에서 지원되는 서울시 POI를 찾을 수 없습니다."
            )

        return self._to_match(nearest_area, "nearest", nearest_distance)

    def find_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float,
        limit: int = 5,
    ) -> list[PoiMatch]:
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("위도 또는 경도의 범위가 올바르지 않습니다.")
        if radius_meters < 0:
            raise ValueError("검색 반경은 0 이상이어야 합니다.")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= self.MAX_NEARBY_RESULTS
        ):
            raise ValueError("주변 POI 결과 수는 1~10 사이의 정수여야 합니다.")

        point = Point(longitude, latitude)
        matches: list[PoiMatch] = []
        for area in self._areas:
            if area.geometry.covers(point):
                match = self._to_match(area, "contains", 0.0)
            else:
                boundary_point = nearest_points(area.geometry, point)[0]
                distance = _distance_meters(point, boundary_point)
                match = self._to_match(area, "nearest", distance)

            if match.distance_meters <= radius_meters:
                matches.append(match)

        matches.sort(
            key=lambda match: (
                match.distance_meters,
                match.area_name,
                match.area_code,
            )
        )
        return matches[:limit]

    @staticmethod
    def _to_match(
        area: _PoiArea,
        match_type: str,
        distance_meters: float,
    ) -> PoiMatch:
        return PoiMatch(
            area_code=area.area_code,
            area_name=area.area_name,
            category=area.category,
            match_type=match_type,
            distance_meters=round(distance_meters, 1),
        )
