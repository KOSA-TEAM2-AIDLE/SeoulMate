import asyncio
import os
import unittest
from unittest.mock import patch

import httpx

from mcp_servers.congestion.server import app, mcp


class CongestionMCPServerTests(unittest.TestCase):
    def test_tool_contract_is_preserved_after_module_split(self):
        tools = asyncio.run(mcp.list_tools())

        self.assertEqual(
            {tool.name for tool in tools},
            {
                "resolve_seoul_place",
                "find_nearby_available_storage_lockers",
                "get_storage_locker_detail",
                "get_nearby_seoul_congestion",
                "get_seoul_congestion",
            },
        )

    def test_gateway_exposes_health_without_authentication(self):
        async def request():
            async with mcp.session_manager.run():
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://test",
                ) as client:
                    return await client.get("/health")

        with patch.dict(os.environ, {}, clear=False):
            response = asyncio.run(request())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "seoul_location_mcp")
        self.assertEqual(response.json()["mcp_endpoint"], "/mcp")


if __name__ == "__main__":
    unittest.main()
