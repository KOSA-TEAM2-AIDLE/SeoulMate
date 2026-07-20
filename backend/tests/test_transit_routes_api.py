import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.routes import router
from services.transit_route_service import TransitProviderError


class TransitRoutesApiTests(unittest.TestCase):
    def test_upstream_transit_auth_failure_is_not_reported_as_missing_route(self) -> None:
        app = FastAPI()
        app.include_router(router)

        with patch(
            "api.routers.routes.transit_route_service.route",
            new=AsyncMock(side_effect=TransitProviderError("ODsay: ApiKey authentication failed")),
        ), TestClient(app) as client:
            response = client.get(
                "/routes/transit",
                params={
                    "origin_lat": 37.5263,
                    "origin_lng": 126.9222,
                    "destination_lat": 37.5302,
                    "destination_lng": 126.9212,
                },
            )

        self.assertEqual(502, response.status_code)
        self.assertIn("ODsay", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
