"""SeoulMate 공용 Weather MCP 서버.

실행::

    python weather_mcp_server.py

MCP 엔드포인트::

    http://127.0.0.1:8001/mcp

기상청 조회와 시간 해석은 독립형 ``KmaWeatherClient``를 재사용한다.
"""

from __future__ import annotations

import asyncio
import hmac
import os
from datetime import date, datetime
from typing import Annotated, Any, Literal

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.responses import JSONResponse

from kma_weather_client import KST, KmaWeatherClient


load_dotenv()

SEOUL_CITY_HALL_LAT = 37.5665
SEOUL_CITY_HALL_LNG = 126.9780

_weather_client = KmaWeatherClient(
    cache_ttl_seconds=int(os.getenv("WEATHER_CACHE_TTL_SECONDS", "600")),
    timeout_seconds=float(os.getenv("WEATHER_TIMEOUT_SECONDS", "15")),
    max_retries=int(os.getenv("WEATHER_MAX_RETRIES", "1")),
)


def build_structured_weather_query(
    query: str,
    target_date: str | None,
    target_time: str | None,
    language: str,
    now: datetime | None = None,
) -> str:
    """구조화 날짜·시간이 있으면 자연어 query보다 우선하는 MCP용 정규 문장을 만든다."""
    if not target_date:
        return query
    current = (now or datetime.now(KST)).astimezone(KST)
    visit_date = date.fromisoformat(str(target_date))
    offset = (visit_date - current.date()).days
    if language == "en":
        day_text = {
            0: "today", 1: "tomorrow", 2: "the day after tomorrow",
            3: "in 3 days", 4: "in 4 days",
        }.get(offset, f"in {offset} days")
    else:
        day_text = {0: "오늘", 1: "내일", 2: "모레", 3: "글피", 4: "그글피"}.get(
            offset, f"{offset}일 뒤"
        )
    return " ".join(part for part in (day_text, target_time or "") if part).strip()

mcp = FastMCP(
    name="seoul_weather_mcp",
    instructions=(
        "서울의 현재 또는 방문 예정 시각 날씨를 제공하는 읽기 전용 도구다. "
        "사용자 질문에 오늘·내일·방문 시간 또는 날씨에 영향을 받는 장소 선택이 있으면 "
        "get_weather_context를 호출한다. 날씨는 후보를 배제하는 절대 기준이 아니라 최종 추천의 "
        "보조 근거로 사용한다. 같은 지역의 후보마다 반복 호출하지 말고 지역당 한 번 호출한다."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/mcp",
)


def build_weather_tags(weather: dict[str, Any]) -> list[str]:
    """도메인과 무관하게 GPT가 해석할 수 있는 안정적인 날씨 태그를 만든다."""
    if not weather.get("available"):
        return []

    tags: list[str] = []
    condition = weather.get("condition")
    temperature = weather.get("temperature_c")
    wind = weather.get("wind_speed_mps")
    precipitation_probability = weather.get("precipitation_probability_pct")

    if condition == "rain":
        tags.append("RAIN")
    elif condition == "snow":
        tags.append("SNOW")

    precipitation_expected = condition in {"rain", "snow"}
    if (
        not precipitation_expected
        and precipitation_probability is not None
        and precipitation_probability >= 60
    ):
        tags.append("PRECIPITATION_LIKELY")
        precipitation_expected = True

    if temperature is not None:
        if temperature >= 28:
            tags.append("HOT")
        elif temperature <= 8:
            tags.append("COLD")

    strong_wind = wind is not None and wind >= 7
    if strong_wind:
        tags.append("STRONG_WIND")

    uncomfortable_temperature = temperature is not None and (
        temperature >= 30 or temperature <= 5
    )
    if precipitation_expected or strong_wind or uncomfortable_temperature:
        tags.extend(("OUTDOOR_UNFAVORABLE", "INDOOR_ACTIVITY_FAVORABLE"))
    elif (
        condition == "clear"
        and temperature is not None
        and 8 < temperature < 28
        and (wind is None or wind < 5)
    ):
        tags.append("OUTDOOR_FAVORABLE")

    if precipitation_expected:
        tags.extend(("SHORT_WALKING_ROUTE_HELPFUL", "PARKING_HELPFUL"))

    return list(dict.fromkeys(tags))


def build_usage_guidance(tags: list[str], language: str) -> list[str]:
    """숙박·카페·문화시설·식당이 공통으로 쓸 수 있는 중립적 힌트를 만든다."""
    tag_set = set(tags)
    if language == "en":
        messages = []
        if "OUTDOOR_UNFAVORABLE" in tag_set:
            messages.append("Prefer places with strong indoor options; treat outdoor features cautiously.")
        if "SHORT_WALKING_ROUTE_HELPFUL" in tag_set:
            messages.append("Shorter walking routes, nearby transit, or parking may be more convenient.")
        if "HOT" in tag_set:
            messages.append("Air-conditioned indoor spaces can be a useful supporting advantage.")
        if "COLD" in tag_set:
            messages.append("Warm indoor spaces can be a useful supporting advantage.")
        if "OUTDOOR_FAVORABLE" in tag_set:
            messages.append("Outdoor or terrace features may be a small supporting advantage.")
        return messages

    messages = []
    if "OUTDOOR_UNFAVORABLE" in tag_set:
        messages.append("실내 선택지가 충분한 장소를 우선 고려하고 야외 시설은 신중하게 평가하세요.")
    if "SHORT_WALKING_ROUTE_HELPFUL" in tag_set:
        messages.append("도보 이동이 짧거나 대중교통·주차 접근성이 좋은 장소가 편리할 수 있습니다.")
    if "HOT" in tag_set:
        messages.append("냉방이 잘 되는 실내 공간은 보조 장점이 될 수 있습니다.")
    if "COLD" in tag_set:
        messages.append("따뜻한 실내 공간은 보조 장점이 될 수 있습니다.")
    if "OUTDOOR_FAVORABLE" in tag_set:
        messages.append("야외 또는 테라스 시설은 소폭의 보조 장점이 될 수 있습니다.")
    return messages


@mcp.tool(
    name="get_weather_context",
    title="Get Seoul weather context",
    description=(
        "Get current weather or a short-term forecast for a Seoul visit. "
        "Use the full user query so Korean/English dates and times can be resolved. "
        "The result contains stable weather codes, localized labels, neutral tags, and guidance "
        "that can supplement accommodation, cafe, cultural-facility, or restaurant answers."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
    structured_output=True,
)
async def get_weather_context(
    query: Annotated[
        str,
        Field(
            description=(
                "The user's complete visit question, including date/time when available; "
                "for example '내일 저녁 카페' or 'a museum tomorrow at 3pm'."
            ),
            max_length=1000,
        ),
    ],
    lat: Annotated[
        float,
        Field(ge=-90, le=90, description="Destination latitude. Defaults to Seoul City Hall."),
    ] = SEOUL_CITY_HALL_LAT,
    lng: Annotated[
        float,
        Field(ge=-180, le=180, description="Destination longitude. Defaults to Seoul City Hall."),
    ] = SEOUL_CITY_HALL_LNG,
    language: Annotated[
        Literal["ko", "en"],
        Field(description="Language for display labels and the short summary."),
    ] = "ko",
    place_name: Annotated[
        str | None,
        Field(description="Optional place or area name used only to identify the returned context."),
    ] = None,
    target_date: Annotated[
        str | None,
        Field(description="Optional ISO visit date (YYYY-MM-DD). When present, it overrides relative dates in query."),
    ] = None,
    target_time: Annotated[
        str | None,
        Field(description="Optional visit time such as evening, 19:00, or 3pm."),
    ] = None,
) -> dict[str, Any]:
    """방문 질문과 좌표에 맞는 현재/예보 날씨를 GPT용 보조 문맥으로 반환한다."""
    resolved_query = build_structured_weather_query(
        query, target_date, target_time, language
    )
    weather = await asyncio.to_thread(
        _weather_client.get_weather,
        lat,
        lng,
        resolved_query,
        None,
        language,
    )
    tags = build_weather_tags(weather)
    result = dict(weather)
    result.update(
        {
            "place_name": place_name or "Seoul",
            "resolved_query": resolved_query,
            "weather_tags": tags,
            "usage_guidance": build_usage_guidance(tags, language),
            "should_affect_recommendation": bool(weather.get("available") and tags),
            "recommendation_policy": (
                "Use weather only as supporting context; do not ignore the user's required conditions "
                "or invent venue features that are absent from candidate data."
                if language == "en"
                else "날씨는 보조 근거로만 사용하고, 사용자 필수 조건을 무시하거나 후보 데이터에 없는 시설을 추측하지 마세요."
            ),
        }
    )
    return result


class WeatherMcpGateway:
    """선택적 Bearer 인증과 상태 확인을 제공하는 순수 ASGI 래퍼."""

    def __init__(self, inner_app: Any):
        self.inner_app = inner_app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == "/health":
                response = JSONResponse(
                    {
                        "ok": True,
                        "service": "seoul_weather_mcp",
                        "mcp_endpoint": "/mcp",
                        "authentication_required": bool(os.getenv("WEATHER_MCP_BEARER_TOKEN")),
                        "kma_api_key_configured": bool(os.getenv("KMA_API_KEY")),
                    }
                )
                await response(scope, receive, send)
                return

            token = os.getenv("WEATHER_MCP_BEARER_TOKEN", "").strip()
            if token and path.startswith("/mcp"):
                headers = {key.lower(): value for key, value in scope.get("headers", [])}
                authorization = headers.get(b"authorization", b"").decode("latin-1")
                expected = f"Bearer {token}"
                if not hmac.compare_digest(authorization, expected):
                    response = JSONResponse(
                        {"error": "Missing or invalid Bearer token."},
                        status_code=401,
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                    await response(scope, receive, send)
                    return

        await self.inner_app(scope, receive, send)


app = WeatherMcpGateway(mcp.streamable_http_app())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("WEATHER_MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("WEATHER_MCP_PORT", "8001")),
        log_level=os.getenv("WEATHER_MCP_LOG_LEVEL", "info").lower(),
    )
