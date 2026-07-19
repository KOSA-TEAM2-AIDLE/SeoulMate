import unittest

from application.recommendation.group_selection import (
    select_grouped_candidates,
)
from application.recommendation.selection_models import (
    CandidateSelection,
    CandidateSelectionResult,
)
from application.recommendation.selection_registry import (
    DomainSelectionRegistry,
)
from domains.common.models import DomainSearchRequest, SearchCandidate


def _candidate(place_id: str, domain: str, task_id: str) -> SearchCandidate:
    return SearchCandidate(
        domain=domain,
        place_id=place_id,
        task_id=task_id,
        name=f"{domain}-{place_id}",
        category=domain,
        base_score=0.8,
        final_score=0.8,
    )


def _wrapped(place_id: str, domain: str, task_id: str) -> dict:
    candidate = _candidate(place_id, domain, task_id)
    return {
        "place_id": place_id,
        "name": candidate.name,
        "payload": {"category": candidate.category},
        "fallback_reason": f"{place_id} 순위 근거",
        "raw_candidate": candidate,
    }


def _request(domain: str, task_id: str) -> DomainSearchRequest:
    return DomainSearchRequest(
        task_id=task_id,
        domain=domain,
        language="ko",
        search_query=f"{domain} 추천",
    )


class StubDomainSelector:
    def __init__(self, domain: str, result: CandidateSelectionResult) -> None:
        self.domain = domain
        self.result = result
        self.calls = []

    async def select(self, request, candidates):
        self.calls.append((request, candidates))
        return self.result


class GroupSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_attraction_uses_only_dspy_selector(self):
        selector = StubDomainSelector(
            "attraction",
            CandidateSelectionResult(
                answer="관광 DSPy 답변",
                selections=[
                    CandidateSelection(
                        place_id="a2",
                        selection_reason="DSPy 선정 이유",
                    ),
                    CandidateSelection(place_id="a1", selection_reason="이유 1"),
                    CandidateSelection(place_id="a3", selection_reason="이유 3"),
                ],
            ),
        )
        registry = DomainSelectionRegistry([selector])
        common_calls = []

        def common_selector(*args):
            common_calls.append(args)
            raise AssertionError("공통 GPT가 호출되면 안 됩니다.")

        result = await select_grouped_candidates(
            message="관광지 추천",
            language="ko",
            task_groups=[{
                "task_id": "task-a",
                "domain": "attraction",
                "candidates": [
                    _wrapped("a1", "attraction", "task-a"),
                    _wrapped("a2", "attraction", "task-a"),
                    _wrapped("a3", "attraction", "task-a"),
                ],
            }],
            requests_by_task={
                "task-a": _request("attraction", "task-a"),
            },
            selection_registry=registry,
            common_selector=common_selector,
        )

        self.assertEqual(common_calls, [])
        self.assertEqual(len(selector.calls), 1)
        self.assertEqual(
            [item.place_id for item in selector.calls[0][1]],
            ["a1", "a2", "a3"],
        )
        self.assertEqual(result["answer"], "관광 DSPy 답변")
        self.assertEqual(
            [
                item["candidate"]["place_id"]
                for item in result["task_results"][0]["selections"]
            ],
            ["a2", "a1", "a3"],
        )

    async def test_groups_without_custom_selector_use_common_gpt_once(self):
        groups = [
            {
                "task_id": "task-r",
                "domain": "restaurant",
                "candidates": [_wrapped("r1", "restaurant", "task-r")],
            },
            {
                "task_id": "task-c",
                "domain": "cafe",
                "candidates": [_wrapped("c1", "cafe", "task-c")],
            },
        ]
        calls = []

        def common_selector(message, language, task_groups, weather, source_mode):
            calls.append((message, language, task_groups, weather, source_mode))
            return {
                "answer": "공통 GPT 답변",
                "task_results": [
                    {
                        "task_id": group["task_id"],
                        "domain": group["domain"],
                        "selections": [{
                            "candidate": group["candidates"][0],
                            "selection_reason": "공통 이유",
                        }],
                    }
                    for group in task_groups
                ],
                "llm_fallback_used": False,
            }

        result = await select_grouped_candidates(
            message="식당과 카페",
            language="ko",
            task_groups=groups,
            requests_by_task={},
            selection_registry=DomainSelectionRegistry(),
            common_selector=common_selector,
            weather={"available": True},
            source_mode="rag_mcp",
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2], groups)
        self.assertEqual(result["answer"], "공통 GPT 답변")
        self.assertEqual(
            [item["task_id"] for item in result["task_results"]],
            ["task-r", "task-c"],
        )

    async def test_mixed_groups_keep_only_valid_attraction_selector_ids(self):
        selector = StubDomainSelector(
            "attraction",
            CandidateSelectionResult(
                answer="관광 답변",
                selections=[
                    CandidateSelection(
                        place_id="invented",
                        selection_reason="잘못된 ID",
                    ),
                    CandidateSelection(place_id="a2", selection_reason="정상 이유"),
                ],
            ),
        )
        attraction_group = {
            "task_id": "task-a",
            "domain": "attraction",
            "candidates": [
                _wrapped("a1", "attraction", "task-a"),
                _wrapped("a2", "attraction", "task-a"),
                _wrapped("a3", "attraction", "task-a"),
            ],
        }
        cafe_group = {
            "task_id": "task-c",
            "domain": "cafe",
            "candidates": [_wrapped("c1", "cafe", "task-c")],
        }

        def common_selector(message, language, task_groups, weather, source_mode):
            self.assertEqual([group["domain"] for group in task_groups], ["cafe"])
            return {
                "answer": "카페 답변",
                "task_results": [{
                    "task_id": "task-c",
                    "domain": "cafe",
                    "selections": [{
                        "candidate": cafe_group["candidates"][0],
                        "selection_reason": "카페 이유",
                    }],
                }],
                "llm_fallback_used": False,
            }

        result = await select_grouped_candidates(
            message="관광지와 카페",
            language="ko",
            task_groups=[attraction_group, cafe_group],
            requests_by_task={"task-a": _request("attraction", "task-a")},
            selection_registry=DomainSelectionRegistry([selector]),
            common_selector=common_selector,
        )

        self.assertEqual(
            [item["task_id"] for item in result["task_results"]],
            ["task-a", "task-c"],
        )
        self.assertEqual(
            [
                item["candidate"]["place_id"]
                for item in result["task_results"][0]["selections"]
            ],
            ["a2"],
        )
        self.assertEqual(result["answer"], "관광 답변\n\n카페 답변")
        self.assertTrue(result["llm_fallback_used"])


if __name__ == "__main__":
    unittest.main()
