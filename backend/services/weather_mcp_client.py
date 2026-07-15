"""백엔드가 로컬 Weather MCP를 호출하는 공용 브리지."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def get_weather_via_mcp(
    query: str,
    lat: float,
    lng: float,
    language: str = "ko",
    place_name: str | None = None,
    *,
    target_date: str | None = None,
    target_time: str | None = None,
) -> dict[str, Any]:
    """로컬/사설 MCP를 호출하고 장애 시 추천을 중단하지 않는 실패 응답을 반환한다."""
    url = os.getenv("WEATHER_MCP_URL", "http://127.0.0.1:8001/mcp")
    token = os.getenv("WEATHER_MCP_BEARER_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else None

    try:
        async with httpx.AsyncClient(headers=headers, timeout=40.0) as http_client:
            async with streamable_http_client(url, http_client=http_client) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    base_arguments = {
                        "query": query,
                        "lat": lat,
                        "lng": lng,
                        "language": "en" if str(language).lower().startswith("en") else "ko",
                        "place_name": place_name,
                    }
                    arguments = dict(base_arguments)
                    if target_date is not None:
                        arguments["target_date"] = target_date
                    if target_time is not None:
                        arguments["target_time"] = target_time
                    call = await session.call_tool("get_weather_context", arguments=arguments)
                    # 실행 중인 구버전 MCP가 새 구조화 인자를 모르면 기존 계약으로 한 번 재시도한다.
                    if call.isError and arguments != base_arguments:
                        call = await session.call_tool(
                            "get_weather_context", arguments=base_arguments
                        )
                    if call.isError:
                        raise RuntimeError("Weather MCP tool returned an error.")
                    if call.structuredContent:
                        return dict(call.structuredContent)
                    if call.content and hasattr(call.content[0], "text"):
                        return json.loads(call.content[0].text)
                    raise RuntimeError("Weather MCP returned no structured content.")
    except Exception as exc:
        return {
            "available": False,
            "is_forecast": False,
            "weather_tags": [],
            "usage_guidance": [],
            "should_affect_recommendation": False,
            "source": "weather-mcp-unavailable",
            "error": str(exc),
        }


__all__ = ["get_weather_via_mcp"]
