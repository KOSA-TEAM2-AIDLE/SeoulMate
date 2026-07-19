import unittest

from domains.attraction.answer_models import AttractionAnswerInput, AttractionEvidenceCandidate
from domains.attraction.dspy.service import AttractionDspyRuntimeService
from domains.attraction.dspy.service import SplitAttractionDspyRuntime
from domains.attraction.selection_service import AttractionSelectionService
from application.recommendation.selection_models import CandidateSelectionResult
from domains.common.models import SearchCandidate


class AttractionDspyRuntimeServiceTests(unittest.TestCase):
    def test_split_runtime_validates_and_renders_two_program_outputs(self):
        class SelectionProgram:
            def __call__(self, **inputs):
                return type("Prediction", (), {
                    "selected_place_ids": ["p1"],
                    "forbidden_place_ids": [],
                    "selection_reasons_json": '{"p1": "전시 근거"}',
                })()

        class AnswerProgram:
            def __call__(self, **inputs):
                return type("Prediction", (), {
                    "structured_answer_json": (
                        '{"language":"ko","recommendations":[{"place_id":"p1",'
                        '"name":"전시장","recommendation_reason":"전시 관람에 좋습니다.",'
                        '"congestion":{"status":"unavailable"},'
                        '"weather":{"status":"unavailable"}}],"no_result_reason":null}'
                    ),
                })()

        result = SplitAttractionDspyRuntime(
            selection_program=SelectionProgram(),
            answer_program=AnswerProgram(),
            lm=None,
        ).run(AttractionAnswerInput(
            question="전시 추천", language="ko",
            candidates=[AttractionEvidenceCandidate(
                place_id="p1", rank=1, name="전시장", category="전시",
            )],
        ))

        self.assertEqual(["p1"], [item.place_id for item in result.selections])
        self.assertIn("전시장", result.answer)

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


if __name__ == "__main__":
    unittest.main()
