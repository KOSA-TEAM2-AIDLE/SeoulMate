import logging

from mcp.server.fastmcp import FastMCP

from core.config import settings
from schemas.congestion import CongestionToolResult
from services.congestion import (
    CongestionService,
    CongestionServiceError,
)
from services.kakao_local import KakaoLocalServiceError
from services.place_resolver import PlaceResolver
from services.poi_matcher import PoiNotSupportedError
from services.storage_lockers import (
    StorageLockerNotFoundError,
    StorageLockerService,
    StorageLockerServiceError,
)

# 공공데이터 인증키가 쿼리스트링에 포함되므로 요청 URL INFO 로그를 막는다.
logging.getLogger("httpx").setLevel(logging.WARNING)

mcp = FastMCP(
    name="SeoulMate Location", # MCP Client에 표시되는 서버 이름이다.
    instructions=(
        "서울 장소명을 위도·경도로 해석하고, 서울시 공식 POI의 "
        "현재 혼잡도와 예측 인구를 조회한다."
    ), # Agent에게 서버의 목적을 설명하는 부분
    host=settings.mcp_server_host, 
    port=settings.mcp_server_port, 
    stateless_http=True, # 요청 간 서버 세션 의존성을 줄인다.
    json_response=True, # 도구 결과를 JSON 구조로 반환하다.
)

congestion_service = CongestionService() # 서비스 객체 생성
place_resolver = PlaceResolver()
storage_locker_service = StorageLockerService()


@mcp.tool()
async def resolve_seoul_place(
    query: str,
    center_latitude: float | None = None,
    center_longitude: float | None = None,
) -> dict:
    """
    사용자가 언급한 서울 시설명을 Kakao Local API로 해석한다.
    명칭이 정확히 일치하면 해당 장소를 selected로 반환한다.
    여러 지점이 있으면 selected는 null이고 requires_disambiguation은 true다.
    중심 좌표를 알고 있으면 위도와 경도를 함께 제공한다.
    """
    has_latitude = center_latitude is not None
    has_longitude = center_longitude is not None
    if has_latitude != has_longitude:
        raise ValueError(
            "center_latitude와 center_longitude는 함께 입력해야 한다."
        )

    try:
        result = await place_resolver.resolve(
            query=query,
            center_latitude=center_latitude,
            center_longitude=center_longitude,
        )
    except ValueError:
        raise
    except KakaoLocalServiceError as error:
        raise RuntimeError(str(error)) from None

    return result.model_dump(mode="json")


@mcp.tool()
async def find_nearby_available_storage_lockers(
    location: str,
    radius_meters: float = 5_000,
) -> dict:
    """
    서울의 장소명을 입력받아 반경 내에서 현재 사용 가능한 물품보관함을
    거리순으로 최대 3개 반환한다. 결과의 locker_id는 상세 조회에 사용한다.
    사용 가능 수는 대형, 중형, 소형 실시간 잔여 수량의 합이다.
    """
    try:
        resolution = await place_resolver.resolve(query=location)
        if resolution.selected is None:
            if resolution.candidates:
                names = ", ".join(
                    candidate.place_name
                    for candidate in resolution.candidates[:5]
                )
                raise ValueError(
                    "장소를 하나로 특정할 수 없습니다. 더 구체적으로 "
                    f"입력해 주세요. 후보: {names}"
                )
            raise ValueError(f"서울에서 장소를 찾을 수 없습니다: {location}")

        selected = resolution.selected
        result = await storage_locker_service.find_nearby_available(
            query=location,
            center_name=selected.place_name,
            latitude=selected.latitude,
            longitude=selected.longitude,
            radius_meters=radius_meters,
        )
    except ValueError:
        raise
    except KakaoLocalServiceError as error:
        raise RuntimeError(str(error)) from None
    except StorageLockerServiceError as error:
        raise RuntimeError(str(error)) from None

    return result.model_dump(mode="json")


@mcp.tool()
async def get_storage_locker_detail(locker_id: str) -> dict:
    """
    물품보관함 ID로 위치, 운영시간, 전체·사용 가능·사용 중 수량,
    크기별 잔여 수량, 요금, 결제수단, 이용방법 등 상세 정보를 반환한다.
    """
    try:
        result = await storage_locker_service.get_detail(locker_id)
    except ValueError:
        raise
    except StorageLockerNotFoundError as error:
        raise ValueError(str(error)) from None
    except StorageLockerServiceError as error:
        raise RuntimeError(str(error)) from None

    return result.model_dump(mode="json")


@mcp.tool()
async def get_nearby_seoul_congestion(
    latitude: float,
    longitude: float,
    radius_meters: float = 3_000,
    limit: int = 5,
) -> dict:
    """
    기준 좌표의 반경 내에 있는 서울시 공식 POI와 실시간 혼잡도를
    거리순으로 반환한다. radius_meters는 미터 단위이며,
    limit은 외부 API 호출량을 제한하기 위해 1~10만 허용한다.
    """
    try:
        result = await congestion_service.get_nearby_congestion(
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
