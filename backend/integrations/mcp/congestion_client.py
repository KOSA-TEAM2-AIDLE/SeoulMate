"""서울 혼잡도 MCP를 공통 ContextProvider 계약으로 감싼다."""

import json
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from integrations.mcp.base_client import ContextRequest, ContextResult
from core.config import settings


def _congestion_mcp_url() -> str:
    return settings.congestion_mcp_url.strip()


def _congestion_mcp_timeout() -> float:
    timeout = settings.congestion_mcp_timeout_seconds
    if timeout <= 0:
        raise ValueError("CONGESTION_MCP_TIMEOUT_SECONDS는 0보다 커야 합니다.")
    return timeout


class CongestionMCPProvider:
    name = "congestion"
    implemented = True
    tool_name = "get_seoul_congestion"

    async def get_context(self, request: ContextRequest) -> ContextResult:
        try:
            token = (
                settings.congestion_mcp_bearer_token.get_secret_value().strip()
                if settings.congestion_mcp_bearer_token is not None
                else ""
            )
            headers = {"Authorization": f"Bearer {token}"} if token else None
            async with httpx.AsyncClient(
                headers=headers,
                timeout=_congestion_mcp_timeout(),
            ) as http_client:
                async with streamable_http_client(
                    _congestion_mcp_url(),
                    http_client=http_client,
                ) as streams:
                    read_stream, write_stream, _ = streams
                    async with ClientSession(
                        read_stream,
                        write_stream,
                    ) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        if self.tool_name not in {
                            tool.name for tool in tools.tools
                        }:
                            raise RuntimeError(
                                "MCP Tool을 찾을 수 없습니다: "
                                f"{self.tool_name}"
                            )
                        result = await session.call_tool(
                            self.tool_name,
                            arguments={
                                "latitude": request.latitude,
                                "longitude": request.longitude,
                            },
                        )
            data = _parse_tool_payload(result)
            return ContextResult(provider=self.name, available=True, data=data)
        except Exception as error:
            return ContextResult(
                provider=self.name,
                available=False,
                error=f"{type(error).__name__}: {error}",
            )


def _parse_tool_payload(result) -> dict:
    if getattr(result, "isError", False):
        messages = [getattr(item, "text", "") for item in (getattr(result, "content", None) or [])]
        raise RuntimeError(" ".join(filter(None, messages)) or "MCP Tool 호출 실패")
    payload = getattr(result, "structuredContent", None)
    if payload is None:
        payload = getattr(result, "structured_content", None)
    if isinstance(payload, dict) and set(payload) == {"result"}:
        payload = payload["result"]
    if payload is None:
        for item in getattr(result, "content", None) or []:
            text = getattr(item, "text", None)
            if not text:
                continue
            try:
                payload = json.loads(text)
                break
            except json.JSONDecodeError:
                continue
    if not isinstance(payload, dict):
        raise RuntimeError("MCP Tool 응답에서 JSON 객체를 찾을 수 없습니다.")
    return payload


__all__ = [
    "CongestionMCPProvider",
    "_congestion_mcp_timeout",
    "_congestion_mcp_url",
]
