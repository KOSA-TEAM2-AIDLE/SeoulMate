import unittest
import time

from domains.attraction.answer_models import (
    AttractionAnswerInput,
    AttractionAnswerResult,
    AttractionEvidenceCandidate,
    AttractionSelection,
)
from domains.attraction.dspy.service import AttractionDspyRuntimeService
from domains.attraction.dspy.service import SplitAttractionDspyRuntime
from domains.attraction.selection_service import AttractionSelectionService
from application.recommendation.selection_models import CandidateSelectionResult
from domains.common.models import SearchCandidate


def _request():
    return type("Request", (), {
        "domain": "attraction", "language": "ko", "location": None,
        "current_location_name": None, "themes": [], "search_query": "전시 추천",
        "context": {},
    })()


def _candidate(place_id="p1"):
    return SearchCandidate(
        domain="attraction", place_id=place_id, task_id="t1", name="전시장",
        category="전시", base_score=1.0, final_score=1.0,
    )


class _LegacyGenerator:
    async def generate(self, **values):
        return AttractionAnswerResult(
            answer="legacy 답변",
            selections=[
                AttractionSelection(place_id="p1", selection_reason="검증 근거")
            ],
        )


class AttractionDspyRuntimeServiceTests(unittest.TestCase):
    def test_split_runtime_renders_server_grounded_context_from_compact_reason_output(self):
        class SelectionProgram:
            def __call__(self, **inputs):
                return type("Prediction", (), {
                    "selected_place_ids": ["p1"],
                    "forbidden_place_ids": [],
                    "selection_reasons_json": '{"p1": "전시 근거"}',
                })()

        class ReasonProgram:
            def __call__(self, **inputs):
                return type("Prediction", (), {
                    "recommendation_reasons_json": '{"p1": "전시 관람에 좋습니다."}',
                })()

        result = SplitAttractionDspyRuntime(
            selection_program=SelectionProgram(),
            reason_program=ReasonProgram(),
            lm=None,
        ).run(AttractionAnswerInput(
            question="전시 추천", language="ko",
            candidates=[AttractionEvidenceCandidate(
                place_id="p1", rank=1, name="전시장", category="전시",
                description="검증된 전시 설명",
                reviews=["검증된 전시 리뷰"],
                congestion={"status": "available", "value": "보통"},
                weather={"status": "available", "value": "condition=clear"},
            )],
        ))

        self.assertEqual(["p1"], [item.place_id for item in result.selections])
        self.assertIn("전시 관람에 좋습니다.", result.selections[0].selection_reason)
        self.assertIn("전시장", result.answer)
        self.assertIn("현재 혼잡도는 보통 수준입니다", result.answer)
        self.assertIn("현재 날씨는 맑음입니다", result.answer)
        self.assertNotIn("혼잡 수준", result.answer)

    def test_returns_fallback_when_artifact_loader_fails(self):
        fallback_calls = []

        def fallback(answer_input):
            fallback_calls.append(answer_input)
            return "fallback"

        service = AttractionDspyRuntimeService(
            artifact_loader=lambda: (_ for _ in ()).throw(FileNotFoundError()),
            fallback=fallback,
        )
        result = service.run(
            AttractionAnswerInput(
                question="전시 추천",
                language="ko",
                candidates=[
                    AttractionEvidenceCandidate(
                        place_id="p1", rank=1, name="전시장", category="전시"
                    )
                ],
            )
        )

        self.assertEqual("fallback", result)
        self.assertEqual(1, len(fallback_calls))


class AttractionSelectionServiceRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_split_runtime_when_it_returns_a_result(self):
        class Runtime:
            def run(self, answer_input):
                return CandidateSelectionResult(answer="새 DSPy 답변", selections=[])

        service = AttractionSelectionService(
            dspy_runtime=Runtime(),
            answer_generator=object(),
        )
        result = await service.select(
            type("Request", (), {
                "domain": "attraction", "language": "ko", "location": None,
                "current_location_name": None, "themes": [], "search_query": "전시",
                "context": {},
            })(),
            [SearchCandidate(
                domain="attraction", place_id="p1", task_id="t1", name="전시장",
                category="전시", base_score=1.0, final_score=1.0,
            )],
        )

        self.assertEqual("새 DSPy 답변", result.answer)

    async def test_split_timeout_uses_legacy_generator(self):
        class SlowRuntime:
            def run(self, answer_input):
                time.sleep(0.05)
                return CandidateSelectionResult(answer="늦은 split", selections=[])

        service = AttractionSelectionService(
            dspy_runtime=SlowRuntime(),
            answer_generator=_LegacyGenerator(),
            split_timeout_seconds=0.001,
        )

        result = await service.select(_request(), [_candidate()])

        self.assertEqual("legacy 답변", result.answer)

    async def test_split_failure_logs_safe_metadata_and_uses_legacy_generator(self):
        class FailingRuntime:
            def run(self, answer_input):
                raise RuntimeError("provider failure")

        service = AttractionSelectionService(
            dspy_runtime=FailingRuntime(),
            answer_generator=_LegacyGenerator(),
            split_timeout_seconds=1,
        )

        with self.assertLogs(
            "domains.attraction.selection_service", level="WARNING"
        ) as captured:
            result = await service.select(_request(), [_candidate()])

        self.assertEqual("legacy 답변", result.answer)
        self.assertIn("attraction_dspy_split_fallback", captured.output[0])
        self.assertIn("error_type=RuntimeError", captured.output[0])
        self.assertNotIn(_request().search_query, captured.output[0])


if __name__ == "__main__":
    unittest.main()
