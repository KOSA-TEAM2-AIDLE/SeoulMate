"""서울 장소·보관함·혼잡도 Tool을 제공하는 독립 MCP 서버."""

from __future__ import annotations

import hmac
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from core.config import settings

from mcp_servers.congestion.tools.congestion import register_congestion_tools
from mcp_servers.congestion.tools.place import register_place_tools
from mcp_servers.congestion.tools.storage_locker import (
    register_storage_locker_tools,
)
from services.congestion import CongestionService
from services.place_resolver import PlaceResolver
from services.storage_lockers import StorageLockerService


logging.getLogger("httpx").setLevel(logging.WARNING)


def _bearer_token() -> str:
    return (
        settings.congestion_mcp_bearer_token.get_secret_value().strip()
        if settings.congestion_mcp_bearer_token is not None
        else ""
    )

mcp = FastMCP(
    name="SeoulMate Location",
    instructions=(
        "서울 장소명을 위도·경도로 해석하고, 주변 물품보관함과 "
        "서울시 공식 POI의 현재 혼잡도를 조회한다."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/mcp",
)

congestion_service = CongestionService()
place_resolver = PlaceResolver()
storage_locker_service = StorageLockerService()

register_place_tools(mcp, place_resolver)
register_storage_locker_tools(
    mcp,
    place_resolver,
    storage_locker_service,
)
register_congestion_tools(mcp, congestion_service)


class LocationMCPGateway:
    """상태 확인과 선택적 Bearer 인증을 제공하는 ASGI 래퍼."""

    def __init__(self, inner_app: Any):
        self.inner_app = inner_app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == "/health":
                response = JSONResponse({
                    "ok": True,
                    "service": "seoul_location_mcp",
                    "mcp_endpoint": "/mcp",
                    "authentication_required": bool(
                        _bearer_token()
                    ),
                })
                await response(scope, receive, send)
                return

            token = _bearer_token()
            if token and path.startswith("/mcp"):
                headers = {
                    key.lower(): value
                    for key, value in scope.get("headers", [])
                }
                authorization = headers.get(
                    b"authorization", b""
                ).decode("latin-1")
                if not hmac.compare_digest(
                    authorization,
                    f"Bearer {token}",
                ):
                    response = JSONResponse(
                        {"error": "Missing or invalid Bearer token."},
                        status_code=401,
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                    await response(scope, receive, send)
                    return
        await self.inner_app(scope, receive, send)


app = LocationMCPGateway(mcp.streamable_http_app())


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=settings.congestion_mcp_host,
        port=settings.congestion_mcp_port,
        log_level=settings.congestion_mcp_log_level.lower(),
    )


if __name__ == "__main__":
    main()


__all__ = ["app", "main", "mcp"]
