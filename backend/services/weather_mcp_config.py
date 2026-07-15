"""도메인 팀이 공통으로 사용하는 OpenAI remote MCP 설정."""

from __future__ import annotations

import os
from typing import Any


WEATHER_MCP_INSTRUCTIONS = """사용자 질문에 현재·미래 방문 시점이 있거나 날씨가 장소 선택에 영향을 줄 수 있으면
get_weather_context를 호출한다. 후보 좌표가 있으면 대표 후보 또는 사용자 목적지 좌표를 전달하고,
없으면 기본 서울 좌표를 사용한다. 같은 지역에 대해 후보마다 반복 호출하지 않는다.
도구의 weather_tags와 usage_guidance는 보조 근거로만 사용한다.
available=false이면 날씨를 추측하거나 언급하지 않는다.
후보 데이터에 없는 실내 시설, 주차, 테라스, 냉난방 여부를 만들어내지 않는다."""


def build_weather_mcp_tool(
    server_url: str | None = None,
    bearer_token: str | None = None,
) -> dict[str, Any]:
    """OpenAI Responses API의 ``tools`` 배열에 넣을 Weather MCP 설정을 반환한다."""
    resolved_url = (server_url or os.getenv("WEATHER_MCP_URL", "")).strip()
    if not resolved_url:
        raise RuntimeError("WEATHER_MCP_URL이 설정되지 않았습니다.")

    tool: dict[str, Any] = {
        "type": "mcp",
        "server_label": "seoul_weather",
        "server_description": (
            "Read-only Seoul weather context for accommodation, cafe, cultural facility, "
            "and restaurant recommendations."
        ),
        "server_url": resolved_url,
        "allowed_tools": ["get_weather_context"],
        "require_approval": "never",
    }
    resolved_token = bearer_token or os.getenv("WEATHER_MCP_BEARER_TOKEN")
    if resolved_token:
        tool["authorization"] = resolved_token
    return tool


__all__ = ["WEATHER_MCP_INSTRUCTIONS", "build_weather_mcp_tool"]

