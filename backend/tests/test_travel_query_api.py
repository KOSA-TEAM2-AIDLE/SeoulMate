import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from api.routers.travel_query import (
    get_travel_query_service_dependency,
    router,
)
from application.travel_query.graph import build_travel_query_graph
from application.travel_query.service import (
    TravelQueryConfigurationError,
    TravelQueryService,
)


def _extraction(inputs: dict) -> dict:
    answer = inputs["latest_user_answer"]
    result = {
        "language": "ko",
        "intent": "day_trip_route",
        "normalized_question": "2026-07-16 홍대 하루 코스",
        "location": "홍대",
        "start_date": "2026-07-16",
    }
    if answer != "none":
        result.update({"pace": "normal", "target_places_per_day": 4})
    return result


class TravelQueryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(router)
        graph = build_travel_query_graph(RunnableLambda(_extraction))
        service = TravelQueryService(graph)
        app.dependency_overrides[
            get_travel_query_service_dependency
        ] = lambda: service
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def test_start_and_resume_keep_same_thread(self) -> None:
        started = self.client.post(
            "/travel-query/start",
            json={
                "message": "내일 홍대 하루 코스 짜줘",
                "language": "ko",
                "reference_at": "2026-07-15T12:00:00+09:00",
            },
        )

        self.assertEqual(200, started.status_code)
        collecting = started.json()
        self.assertEqual("collecting", collecting["status"])
        self.assertEqual(
            ["route_request.target_places_per_day"],
            collecting["missing_fields"],
        )

        resumed = self.client.post(
            f"/travel-query/{collecting['thread_id']}/resume",
            json={"answer": "보통"},
        )

        self.assertEqual(200, resumed.status_code)
        ready = resumed.json()
        self.assertEqual(collecting["thread_id"], ready["thread_id"])
        self.assertEqual("ready", ready["status"])
        self.assertEqual(
            4,
            ready["structured_query"]["route_request"]["target_places_per_day"],
        )
        self.assertEqual(1, len(ready["agent_dispatches"]))
        self.assertEqual("etc", ready["agent_dispatches"][0]["domain"])
        self.assertEqual(
            ["task_1", "task_2", "task_3", "task_4"],
            ready["agent_dispatches"][0]["task_ids"],
        )

        completed = self.client.post(
            f"/travel-query/{collecting['thread_id']}/resume",
            json={"answer": "다시 답변"},
        )
        self.assertEqual(409, completed.status_code)

    def test_unknown_thread_returns_not_found(self) -> None:
        response = self.client.post(
            "/travel-query/not-found/resume",
            json={"answer": "보통"},
        )

        self.assertEqual(404, response.status_code)

    def test_naive_reference_time_is_rejected(self) -> None:
        response = self.client.post(
            "/travel-query/start",
            json={
                "message": "홍대 카페 추천",
                "reference_at": "2026-07-15T12:00:00",
            },
        )

        self.assertEqual(422, response.status_code)

    def test_missing_model_configuration_returns_service_unavailable(self) -> None:
        app = FastAPI()
        app.include_router(router)
        with patch(
            "api.routers.travel_query.get_travel_query_service",
            side_effect=TravelQueryConfigurationError("missing key"),
        ), TestClient(app) as client:
            response = client.post(
                "/travel-query/start",
                json={"message": "홍대 카페 추천"},
            )

        self.assertEqual(503, response.status_code)


if __name__ == "__main__":
    unittest.main()
