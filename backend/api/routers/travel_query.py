from fastapi import APIRouter, Depends, HTTPException, status

from application.travel_query.service import (
    TravelQueryConfigurationError,
    TravelQueryExecutionError,
    TravelQueryService,
    TravelQueryThreadCompletedError,
    TravelQueryThreadNotFoundError,
    get_travel_query_service,
)
from schemas.travel_query_api import (
    TravelQueryApiResponse,
    TravelQueryResumeRequest,
    TravelQueryStartRequest,
)


router = APIRouter(prefix="/travel-query", tags=["travel-query"])


def get_travel_query_service_dependency() -> TravelQueryService:
    try:
        return get_travel_query_service()
    except TravelQueryConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/start", response_model=TravelQueryApiResponse)
async def start_travel_query(
    body: TravelQueryStartRequest,
    service: TravelQueryService = Depends(get_travel_query_service_dependency),
) -> TravelQueryApiResponse:
    try:
        return await service.start(body)
    except TravelQueryExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": str(exc), "errors": exc.errors},
        ) from exc


@router.post("/{thread_id}/resume", response_model=TravelQueryApiResponse)
async def resume_travel_query(
    thread_id: str,
    body: TravelQueryResumeRequest,
    service: TravelQueryService = Depends(get_travel_query_service_dependency),
) -> TravelQueryApiResponse:
    try:
        return await service.resume(
            thread_id,
            body.answer,
            current_latitude=body.lat,
            current_longitude=body.lng,
        )
    except TravelQueryThreadNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 travel-query thread를 찾을 수 없습니다.",
        ) from exc
    except TravelQueryThreadCompletedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 완료된 travel-query thread입니다.",
        ) from exc
    except TravelQueryExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": str(exc), "errors": exc.errors},
        ) from exc
