from mcp.server.fastmcp import FastMCP

from core.config import settings
from schemas.congestion import CongestionToolResult
from services.congestion import (
    CongestionService,
    CongestionServiceError,
)
from services.poi_matcher import PoiNotSupportedError

mcp = FastMCP(
    name="SeoulMate Congestion", # MCP Client에 표시되는 서버 이름이다.
    instructions=(
        "서울시 공식 POI의 현재 혼잡도와 예측 인구를 조회한다. "
        "장소명, POI 코드 또는 위도·경도를 사용할 수 있다."
    ), # Agent에게 서버의 목적을 설명하는 부분
    host=settings.mcp_server_host, 
    port=settings.mcp_server_port, 
    stateless_http=True, # 요청 간 서버 세션 의존성을 줄인다.
    json_response=True, # 도구 결과를 JSON 구조로 반환하다.
)

congestion_service = CongestionService() # 서비스 객체 생성 

@mcp.tool()
async def get_seoul_congestion(
    area: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """
    서울시 공식 POI의 실시간 혼잡도를 조회한다.
    장소명 또는 POI 코드를 알고 있으면 area를 사용한다.
    사용자 위치를 알고 있으면 latitude와 longitude를 함께 사용한다.
    좌표와 area가 모두 제공되면 좌표를 우선 사용한다.
    """
    has_latitude = latitude is not None
    has_longitude = longitude is not None

    if has_latitude != has_longitude:
        raise ValueError(
            "latitude와 longitude는 함께 입력해야 한다."
        )

    try :
        if has_latitude and has_longitude : 
            location_result = (
                await congestion_service.get_congestion_by_location(
                    latitude = latitude,
                    longitude = longitude
                )
            )

            result = CongestionToolResult(
                query_type = "location",
                poi_match = location_result.poi_match,
                congestion = location_result.congestion
            )
        
        elif area is not None and area.strip():
            snapshot = await congestion_service.get_congestion(
                area.strip()
            )

            result = CongestionToolResult(
                query_type = "area",
                poi_match = None,
                congestion = snapshot
            )
        else :
            raise ValueError(
                "area 또는 latitude와 longitude가 필요하다"
            )

    # MCP ERROR 인지, API 에러 인지 구분짓기 위함
    except PoiNotSupportedError as error : 
        raise ValueError(str(error)) from None
    except CongestionServiceError as error : 
        raise RuntimeError(str(error)) from None
    
    return result.model_dump(mode="json")

def main() -> None :
    mcp.run(transport = "streamable-http")

if __name__ == "__main__" :
    main()