import unittest
from datetime import date

from application.recommendation.candidate_selector import validate_selected_ids
from application.recommendation.request_factory import build_domain_search_request
from domains.common.exceptions import DomainNotImplementedError
from domains.common.models import DomainSearchRequest, SearchCandidate
from domains.common.registry import build_default_domain_registry
from integrations.mcp.registry import build_default_context_registry
from schemas.structured_query import StructuredQueryTask, StructuredTravelQuery


def candidate(place_id: str) -> SearchCandidate:
    return SearchCandidate(
        domain="restaurant",
        place_id=place_id,
        task_id="task_1",
        name=f"식당 {place_id}",
        category="한식",
        base_score=1.0,
        final_score=1.0,
    )


class TargetArchitectureTests(unittest.IsolatedAsyncioTestCase):
    def test_default_registry_marks_only_real_implementations_ready(self):
        self.assertEqual(
            build_default_domain_registry().status(),
            {
                "accommodation": False,
                "attraction": True,
                "cafe": False,
                "restaurant": True,
                "storage_locker": False,
            },
        )
        self.assertEqual(
            build_default_context_registry().status(),
            {"congestion": False, "weather": True},
        )

    async def test_skeleton_service_fails_explicitly(self):
        service = build_default_domain_registry().get("cafe")
        request = DomainSearchRequest(
            task_id="task_1",
            domain="cafe",
            search_query="조용한 카페",
        )
        with self.assertRaises(DomainNotImplementedError):
            await service.search(request)

    def test_request_factory_uses_task_filters_and_keeps_structured_context(self):
        parsed = StructuredTravelQuery.model_validate({
            "language": "ko",
            "intent": "single_place_recommendation",
            "original_question": "내일 홍대에서 주차 가능한 식당",
            "normalized_question": "홍대 주차 가능 식당",
            "filters": {"location": "서울", "start_date": "2026-07-16"},
            "tasks": [{
                "task_id": "task_1",
                "domain": "restaurant",
                "search_query": "홍대 주차 가능한 식당",
                "themes": ["주차"],
                "filters": {"location": "홍대", "required_features": ["주차"]},
            }],
        })
        request = build_domain_search_request(parsed, parsed.tasks[0])
        self.assertEqual(request.location, "홍대")
        self.assertEqual(request.visit_date, date(2026, 7, 16))
        self.assertIn("주차", request.required_features)
        self.assertIs(request.context["parsed_query"], parsed)

    def test_candidate_selector_repairs_invalid_and_duplicate_gpt_ids(self):
        candidates = [candidate("1"), candidate("2"), candidate("3")]
        selected = validate_selected_ids(
            candidates,
            ["restaurant:404", "restaurant:2", "restaurant:2"],
            limit=2,
        )
        self.assertEqual([item.place_id for item in selected], ["2", "1"])


if __name__ == "__main__":
    unittest.main()
