"""내부/프론트 공용 날씨 문맥 API. 향후 MCP도 이 엔드포인트를 감싼다."""

import asyncio

from fastapi import APIRouter, Query

from services.weather import get_weather_context, get_weather_for_query


router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/context")
async def weather_context(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    query: str | None = Query(None, description="오늘 저녁·내일 등 방문 시점이 포함된 질의"),
):
    if query:
        return await asyncio.to_thread(get_weather_for_query, query, lat, lng)
    return await asyncio.to_thread(get_weather_context, lat, lng)
