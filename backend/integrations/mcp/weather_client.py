"""운영 중인 Weather MCP client의 공통 Provider 어댑터."""

from integrations.mcp.base_client import ContextRequest, ContextResult
from services.weather_mcp_client import get_weather_via_mcp


class WeatherMCPProvider:
    name = "weather"
    implemented = True

    async def get_context(self, request: ContextRequest) -> ContextResult:
        data = await get_weather_via_mcp(
            request.query,
            request.latitude,
            request.longitude,
            request.language,
            request.place_name,
            target_date=request.target_date,
            target_time=request.target_time,
        )
        return ContextResult(
            provider=self.name,
            available=bool(data.get("available")),
            data=data,
            error=data.get("error"),
        )


__all__ = ["WeatherMCPProvider", "get_weather_via_mcp"]

