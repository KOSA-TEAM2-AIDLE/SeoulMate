"""외부 도구 어댑터. 날씨는 커스텀 서비스 호출 후 향후 MCP로 노출한다."""
from typing import Optional
from schemas.common import ToolResult
from services.weather import get_weather_context


def get_congestion(area_code: str, place_name: Optional[str] = None) -> ToolResult:
    """서울시 실시간 인구 밀집도 조회."""
    raise NotImplementedError


def get_weather(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    place_name: Optional[str] = None,
) -> ToolResult:
    """기상청 좌표 기반 현재 날씨 조회. MCP가 아닌 내부 서비스가 원본이다."""
    if lat is None or lng is None:
        return ToolResult(
            tool_name="get_weather",
            params={"lat": lat, "lng": lng, "place_name": place_name},
            result={},
            ok=False,
            source="mock",
            error="lat과 lng가 필요합니다.",
        )
    result = get_weather_context(lat, lng)
    return ToolResult(
        tool_name="get_weather",
        params={"lat": lat, "lng": lng, "place_name": place_name},
        result={key: value for key, value in result.items() if key != "error"},
        ok=bool(result.get("available")),
        source="live" if result.get("available") else "mock",
        error=result.get("error"),
    )


def get_hotel_availability(
    destination: str,
    checkin_date: str,
    checkout_date: str,
    number_of_adults: Optional[int] = None,
) -> ToolResult:
    """Booking.com MCP 숙박 가용성 조회."""
    raise NotImplementedError


def call_tool(tool_name: str, params: dict) -> ToolResult:
    """/actions 엔드포인트에서 사용하는 단일 진입점 디스패처."""
    if tool_name == "get_weather":
        return get_weather(**params)
    if tool_name == "get_congestion":
        return get_congestion(**params)
    if tool_name == "get_hotel_availability":
        return get_hotel_availability(**params)
    return ToolResult(
        tool_name=tool_name,
        params=params,
        result={},
        ok=False,
        source="mock",
        error="지원하지 않는 도구입니다.",
    )
