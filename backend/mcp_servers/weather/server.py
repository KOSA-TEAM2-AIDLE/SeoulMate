"""새 구조의 Weather MCP ASGI 진입점.

실행: ``uvicorn mcp_servers.weather.server:app --host 127.0.0.1 --port 8001``
"""

from weather_mcp_server import app, mcp

__all__ = ["app", "mcp"]

