"""API 명세서 3-2, 3-4 참고. 1단계: mock 응답. 2단계: 실제 MCP 서버(서울 열린데이터, 기상청, Booking.com) 연결."""
from typing import Optional
from schemas.common import ToolResult


def get_congestion(area_code: str, place_name: Optional[str] = None) -> ToolResult:
    """서울시 실시간 인구 밀집도 조회."""
    raise NotImplementedError


def get_weather(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    place_name: Optional[str] = None,
) -> ToolResult:
    """기상청 좌표 기반 현재 날씨 조회."""
    raise NotImplementedError


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
    raise NotImplementedError
