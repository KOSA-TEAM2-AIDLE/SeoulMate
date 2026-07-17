from mcp.server.fastmcp import FastMCP

from schemas.congestion import CongestionToolResult
from services.congestion import CongestionService, CongestionServiceError
from services.poi_matcher import PoiNotSupportedError


def register_congestion_tools(
    mcp: FastMCP,
    service: CongestionService,
) -> None:
    @mcp.tool()
    async def get_nearby_seoul_congestion(
        latitude: float,
        longitude: float,
        radius_meters: float = 3_000,
        limit: int = 5,
    ) -> dict:
        """기준 좌표 반경 내 서울시 공식 POI와 실시간 혼잡도를 반환한다."""
        try:
            result = await service.get_nearby_congestion(
                latitude=latitude,
                longitude=longitude,
                radius_meters=radius_meters,
                limit=limit,
            )
        except ValueError:
            raise
        except CongestionServiceError as error:
            raise RuntimeError(str(error)) from None
        return result.model_dump(mode="json")

    @mcp.tool()
    async def get_seoul_congestion(
        area: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> dict:
        """장소명 또는 좌표로 서울시 공식 POI의 실시간 혼잡도를 조회한다."""
        has_latitude = latitude is not None
        has_longitude = longitude is not None
        if has_latitude != has_longitude:
            raise ValueError("latitude와 longitude는 함께 입력해야 한다.")
        try:
            if has_latitude and has_longitude:
                location_result = await service.get_congestion_by_location(
                    latitude=latitude,
                    longitude=longitude,
                )
                result = CongestionToolResult(
                    query_type="location",
                    poi_match=location_result.poi_match,
                    congestion=location_result.congestion,
                )
            elif area is not None and area.strip():
                result = CongestionToolResult(
                    query_type="area",
                    poi_match=None,
                    congestion=await service.get_congestion(area.strip()),
                )
            else:
                raise ValueError(
                    "area 또는 latitude와 longitude가 필요하다"
                )
        except PoiNotSupportedError as error:
            raise ValueError(str(error)) from None
        except CongestionServiceError as error:
            raise RuntimeError(str(error)) from None
        return result.model_dump(mode="json")


__all__ = ["register_congestion_tools"]
