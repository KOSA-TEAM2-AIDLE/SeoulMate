from mcp.server.fastmcp import FastMCP

from services.kakao_local import KakaoLocalServiceError
from services.place_resolver import PlaceResolver


def register_place_tools(mcp: FastMCP, resolver: PlaceResolver) -> None:
    @mcp.tool()
    async def resolve_seoul_place(
        query: str,
        center_latitude: float | None = None,
        center_longitude: float | None = None,
    ) -> dict:
        """사용자가 언급한 서울 시설명을 Kakao Local API로 해석한다."""
        has_latitude = center_latitude is not None
        has_longitude = center_longitude is not None
        if has_latitude != has_longitude:
            raise ValueError(
                "center_latitude와 center_longitude는 함께 입력해야 한다."
            )
        try:
            result = await resolver.resolve(
                query=query,
                center_latitude=center_latitude,
                center_longitude=center_longitude,
            )
        except ValueError:
            raise
        except KakaoLocalServiceError as error:
            raise RuntimeError(str(error)) from None
        return result.model_dump(mode="json")


__all__ = ["register_place_tools"]
