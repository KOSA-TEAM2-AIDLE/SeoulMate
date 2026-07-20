import asyncio
import os
import unittest
from datetime import datetime
from unittest.mock import patch

import httpx

from kma_weather_client import KST
from services.weather_mcp_config import build_weather_mcp_tool
from weather_mcp_server import (
    _weather_client,
    app,
    build_weather_tags,
    build_structured_weather_query,
    get_weather_context,
    mcp,
)


class WeatherMcpServerTests(unittest.TestCase):
    def test_structured_date_overrides_conflicting_query_date(self):
        query = build_structured_weather_query(
            "tomorrow evening",
            "2026-07-16",
            "15:00",
            "en",
            now=datetime(2026, 7, 14, 12, 0, tzinfo=KST),
        )
        self.assertEqual(query, "the day after tomorrow 15:00")

    def test_tool_schema_is_structured_and_read_only(self):
        tools = asyncio.run(mcp.list_tools())
        self.assertEqual([tool.name for tool in tools], ["get_weather_context"])
        tool = tools[0]
        self.assertTrue(tool.annotations.readOnlyHint)
        self.assertFalse(tool.annotations.destructiveHint)
        self.assertTrue(tool.annotations.idempotentHint)
        self.assertIn("query", tool.inputSchema["required"])
        self.assertIsNotNone(tool.outputSchema)

    def test_weather_tags_are_domain_neutral(self):
        tags = build_weather_tags(
            {
                "available": True,
                "condition": "rain",
                "temperature_c": 31,
                "wind_speed_mps": 8,
                "precipitation_probability_pct": 80,
            }
        )
        self.assertIn("RAIN", tags)
        self.assertIn("HOT", tags)
        self.assertIn("STRONG_WIND", tags)
        self.assertIn("OUTDOOR_UNFAVORABLE", tags)
        self.assertIn("INDOOR_ACTIVITY_FAVORABLE", tags)
        self.assertIn("PARKING_HELPFUL", tags)

    def test_tool_returns_guidance_without_domain_specific_facts(self):
        weather = {
            "available": True,
            "condition": "rain",
            "condition_label": "비",
            "temperature_c": 24.0,
            "wind_speed_mps": 2.0,
            "precipitation_probability_pct": 70.0,
            "summary": "내일 저녁: 비, 24°C입니다.",
            "language": "ko",
        }
        with patch.object(_weather_client, "get_weather", return_value=weather):
            result = asyncio.run(
                get_weather_context(
                    query="내일 저녁 문화시설",
                    language="ko",
                    place_name="종로",
                )
            )
        self.assertEqual(result["place_name"], "종로")
        self.assertTrue(result["should_affect_recommendation"])
        self.assertIn("RAIN", result["weather_tags"])
        self.assertTrue(result["usage_guidance"])

    def test_openai_remote_mcp_config(self):
        tool = build_weather_mcp_tool(
            "https://weather.example.com/mcp",
            "test-token",
        )
        self.assertEqual(tool["type"], "mcp")
        self.assertEqual(tool["allowed_tools"], ["get_weather_context"])
        self.assertEqual(tool["require_approval"], "never")
        self.assertEqual(tool["authorization"], "test-token")

    def test_gateway_health_and_bearer_auth(self):
        async def request():
            async with mcp.session_manager.run():
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    health = await client.get("/health")
                    unauthorized = await client.post("/mcp")
                    authorized = await client.post(
                        "/mcp",
                        headers={"Authorization": "Bearer test-token"},
                    )
                    return health, unauthorized, authorized

        with patch.dict(os.environ, {"WEATHER_MCP_BEARER_TOKEN": "test-token"}):
            health, unauthorized, authorized = asyncio.run(request())
        self.assertEqual(health.status_code, 200)
        self.assertEqual(unauthorized.status_code, 401)
        self.assertNotEqual(authorized.status_code, 401)


if __name__ == "__main__":
    unittest.main()
