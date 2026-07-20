import unittest
from unittest.mock import patch

from integrations.mcp.congestion_client import (
    _congestion_mcp_timeout,
    _congestion_mcp_url,
)


class CongestionMCPClientConfigTests(unittest.TestCase):
    def test_client_uses_dedicated_url(self):
        with patch(
            "integrations.mcp.congestion_client.settings.congestion_mcp_url",
            "http://localhost:9123/mcp",
        ):
            self.assertEqual(
                _congestion_mcp_url(),
                "http://localhost:9123/mcp",
            )

    def test_client_has_configurable_positive_timeout(self):
        with patch(
            "integrations.mcp.congestion_client.settings.congestion_mcp_timeout_seconds",
            12.5,
        ):
            self.assertEqual(_congestion_mcp_timeout(), 12.5)

        with patch(
            "integrations.mcp.congestion_client.settings.congestion_mcp_timeout_seconds",
            0,
        ):
            with self.assertRaisesRegex(ValueError, "0보다 커야"):
                _congestion_mcp_timeout()


if __name__ == "__main__":
    unittest.main()
