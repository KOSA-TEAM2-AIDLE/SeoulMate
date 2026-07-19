import json
import unittest
from unittest.mock import patch

from application.recommendation.domain_executor import DomainSearchBatch
from application.recommendation.selection_models import (
    CandidateSelection,
    CandidateSelectionResult,
)
from application.recommendation.selection_registry import DomainSelectionRegistry
from domains.common.models import SearchCandidate
from routers.chat import _multi_task_recommendation_stream
from schemas.chat import ChatRequest


class _AttractionSelector:
    domain = "attraction"

    def __init__(self) -> None:
        self.calls = 0

    async def select(self, request, candidates):
        self.calls += 1
        return CandidateSelectionResult(
            answer="DSPy가 작성한 관광 답변",
            selections=[
                CandidateSelection(
                    place_id="attraction-1",
                    selection_reason="전시 주제와 검증된 설명이 맞습니다.",
                )
            ],
        )


class AttractionDspyChatIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_attraction_selector_reason_and_answer_reach_chat_sse(self):
        candidate = SearchCandidate(
            domain="attraction",
            place_id="attraction-1",
            task_id="task-attraction",
            name="테스트 전시장",
            category="전시",
            base_score=0.9,
            final_score=0.9,
            evidence=["검증된 전시 설명"],
        )
        body = ChatRequest.model_validate(
            {
                "message": "서울 전시 추천",
                "lang": "ko",
                "parsed_query": {
                    "language": "ko",
                    "intent": "single_place_recommendation",
                    "original_question": "서울 전시 추천",
                    "normalized_question": "서울 전시 추천",
                    "tasks": [
                        {
                            "task_id": "task-attraction",
                            "domain": "attraction",
                            "search_query": "서울 전시",
                            "desired_count": 1,
                        }
                    ],
                    "filters": {"location": "서울"},
                },
            }
        )
        selector = _AttractionSelector()

        async def fake_search(*args, **kwargs):
            return DomainSearchBatch(
                task_id="task-attraction",
                domain="attraction",
                candidates=[candidate],
                source_kind="live",
                sources=["attraction-search-service"],
            )

        async def fake_rerank(candidates, parsed, source_mode, request):
            return candidates, ()

        with (
            patch("routers.chat._search_structured_task", fake_search),
            patch("routers.chat._rerank_attraction_candidates", fake_rerank),
            patch(
                "routers.chat.domain_selection_registry",
                DomainSelectionRegistry([selector]),
            ),
        ):
            events = [
                event
                async for event in _multi_task_recommendation_stream(
                    body,
                    "rag_only",
                    "test routing",
                )
            ]

        meta = json.loads(events[0].removeprefix("data: ").strip())
        token = json.loads(events[1].removeprefix("data: ").strip())
        self.assertEqual(1, selector.calls)
        self.assertEqual(
            "전시 주제와 검증된 설명이 맞습니다.",
            meta["places"][0]["selection_reason"],
        )
        self.assertEqual("DSPy가 작성한 관광 답변", token["text"])


if __name__ == "__main__":
    unittest.main()

