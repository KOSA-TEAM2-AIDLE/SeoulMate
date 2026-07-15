import unittest

from application.recommendation.domain_dispatcher import (
    DomainAgentRegistry,
    ReadyDomainAgentDispatcher,
    build_temporary_agent_registry,
)
from domains.accommodation.agent import AccommodationAgent
from domains.attraction.agent import AttractionAgent
from domains.cafe.agent import CafeAgent
from domains.etc.agent import EtcAgent
from domains.restaurant.agent import RestaurantAgent
from schemas.travel_query_api import (
    DomainAgentDispatchResult,
    TravelQueryApiResponse,
)


def _ready_response() -> TravelQueryApiResponse:
    return TravelQueryApiResponse.model_validate(
        {
            "thread_id": "dispatch-thread-1",
            "status": "ready",
            "structured_query": {
                "language": "ko",
                "intent": "day_trip_route",
                "original_question": "홍대에서 식당과 카페 코스를 추천해줘",
                "normalized_question": "홍대 식당, 카페, 식당 순서의 코스 추천",
                "tasks": [
                    {
                        "task_id": "task_1",
                        "domain": "restaurant",
                        "search_query": "홍대 식당",
                        "desired_count": 1,
                        "day_number": 1,
                        "visit_date": "2026-07-16",
                    },
                    {
                        "task_id": "task_2",
                        "domain": "cafe",
                        "search_query": "홍대 카페",
                        "desired_count": 1,
                        "day_number": 1,
                        "visit_date": "2026-07-16",
                    },
                    {
                        "task_id": "task_3",
                        "domain": "restaurant",
                        "search_query": "홍대 저녁 식당",
                        "desired_count": 1,
                        "day_number": 1,
                        "visit_date": "2026-07-16",
                    },
                ],
                "filters": {
                    "location": "홍대",
                    "start_date": "2026-07-16",
                    "end_date": "2026-07-16",
                },
                "route_request": {
                    "destination": "홍대",
                    "period": {
                        "start_date": "2026-07-16",
                        "end_date": "2026-07-16",
                        "nights": 0,
                        "days": 1,
                    },
                    "max_places_per_day": 5,
                    "target_places_per_day": 3,
                },
            },
        }
    )


class RecordingAgent:
    def __init__(self, domain: str) -> None:
        self.domain = domain
        self.received: list[TravelQueryApiResponse] = []

    async def execute(
        self,
        response: TravelQueryApiResponse,
    ) -> DomainAgentDispatchResult:
        self.received.append(response)
        task_ids = [
            task.task_id
            for task in response.structured_query.tasks
            if task.domain == self.domain
        ]
        return DomainAgentDispatchResult(
            domain=self.domain,
            task_ids=task_ids,
            assistant_message="recorded",
        )


class ReadyDomainAgentDispatcherTests(unittest.IsolatedAsyncioTestCase):
    def test_default_registry_uses_separate_domain_agent_classes(self) -> None:
        registry = build_temporary_agent_registry()

        self.assertIsInstance(registry.get("restaurant"), RestaurantAgent)
        self.assertIsInstance(registry.get("cafe"), CafeAgent)
        self.assertIsInstance(registry.get("accommodation"), AccommodationAgent)
        self.assertIsInstance(registry.get("attraction"), AttractionAgent)
        self.assertIsInstance(registry.get("etc"), EtcAgent)

    async def test_calls_only_domains_in_tasks_once_with_full_response(self) -> None:
        restaurant = RecordingAgent("restaurant")
        cafe = RecordingAgent("cafe")
        accommodation = RecordingAgent("accommodation")
        dispatcher = ReadyDomainAgentDispatcher(
            DomainAgentRegistry([restaurant, cafe, accommodation])
        )
        response = _ready_response()

        results = await dispatcher.dispatch(response)

        self.assertEqual(["restaurant", "cafe"], [item.domain for item in results])
        self.assertEqual(1, len(restaurant.received))
        self.assertEqual(1, len(cafe.received))
        self.assertEqual(0, len(accommodation.received))
        self.assertIs(response, restaurant.received[0])
        self.assertIs(response, cafe.received[0])
        self.assertEqual(["task_1", "task_3"], results[0].task_ids)
        self.assertEqual(["task_2"], results[1].task_ids)

    async def test_collecting_response_does_not_call_agents(self) -> None:
        restaurant = RecordingAgent("restaurant")
        dispatcher = ReadyDomainAgentDispatcher(
            DomainAgentRegistry([restaurant])
        )
        response = TravelQueryApiResponse(
            thread_id="collecting-thread",
            status="collecting",
            assistant_message="어느 지역에서 찾을까요?",
            missing_fields=["filters.location"],
        )

        results = await dispatcher.dispatch(response)

        self.assertEqual([], results)
        self.assertEqual([], restaurant.received)

    async def test_placeholder_agent_reports_received_tasks(self) -> None:
        results = await ReadyDomainAgentDispatcher().dispatch(_ready_response())

        self.assertEqual(["restaurant", "cafe"], [item.domain for item in results])
        self.assertEqual(["task_1", "task_3"], results[0].task_ids)
        self.assertEqual("placeholder", results[0].status)


if __name__ == "__main__":
    unittest.main()
