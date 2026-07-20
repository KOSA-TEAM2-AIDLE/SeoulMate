"""저장 루트 CRUD endpoint 스켈레톤.

루트 생성·수정은 현재 POST /chat SSE에서 동작한다. 팀의 영속화 API 명세가 확정되면
이 router에 저장/조회/삭제 endpoint를 추가하고 application.route만 호출한다.
"""
from fastapi import APIRouter, HTTPException, Query

from schemas.transit import TransitPoint, TransitSegment
from services.transit_route_service import TransitProviderError, transit_route_service

router = APIRouter(prefix="/routes", tags=["routes"])


@router.get("/transit", response_model=TransitSegment)
async def get_transit_route(
    origin_lat: float = Query(...), origin_lng: float = Query(...),
    destination_lat: float = Query(...), destination_lng: float = Query(...),
    language: str = Query("en", pattern="^(ko|en)$"),
):
    try:
        return await transit_route_service.route(
            TransitPoint(lat=origin_lat, lng=origin_lng),
            TransitPoint(lat=destination_lat, lng=destination_lng), language,
        )
    except TransitProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/transit/geometry")
async def get_transit_geometry(map_object: str = Query(..., min_length=1)):
    try:
        return await transit_route_service.lane_geometry(map_object)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

__all__ = ["router"]
