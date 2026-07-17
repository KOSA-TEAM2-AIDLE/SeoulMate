import time
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from domains.attraction import AttractionAnswerGenerator, AttractionRecommendationPipeline
from domains.attraction.answer_models import AttractionAnswerResult, AttractionSelection
from application.recommendation.selection_models import (
    CandidateSelection,
    CandidateSelectionResult,
)
from domains.common.models import DomainSearchRequest, SearchCandidate
from domains.attraction.answer_program import (
    AttractionProgramArtifactError,
    AttractionSelectionAnswerProgram,
    AttractionSelectionAnswerSignature,
    load_attraction_program,
)


class AttractionSelectionAnswerSignatureTests(unittest.TestCase):
    def test_signature_has_stable_input_and_output_contract(self):
        self.assertEqual(
            list(AttractionSelectionAnswerSignature.input_fields),
            [
                "language",
                "question",
                "location",
                "themes_json",
                "selection_count",
                "candidates_json",
            ],
        )
        self.assertEqual(
            list(AttractionSelectionAnswerSignature.output_fields),
            ["selected_place_ids", "selection_reasons_json", "answer"],
        )

    def test_signature_instructions_include_grounding_and_language_rules(self):
        instructions = AttractionSelectionAnswerSignature.instructions

        self.assertIn("사용자의 언어", instructions)
        self.assertIn("후보에 제공된 근거", instructions)
        self.assertIn("시설 내부 인파", instructions)
        self.assertIn("혼잡도 근거가 없으면", instructions)


class AttractionProgramLoaderTests(unittest.TestCase):
    def test_missing_artifact_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"

            with self.assertRaises(FileNotFoundError):
                load_attraction_program(missing)

    def test_corrupt_artifact_raises_domain_error(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "corrupt.json"
            artifact.write_text("{broken", encoding="utf-8")

            with self.assertRaises(AttractionProgramArtifactError):
                load_attraction_program(artifact)

    def test_loader_only_restores_artifact_without_running_optimizer(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "program.json"
            AttractionSelectionAnswerProgram().save(artifact)

            with patch("dspy.MIPROv2", side_effect=AssertionError("optimizer called")):
                loaded = load_attraction_program(artifact)

        self.assertIsInstance(loaded, AttractionSelectionAnswerProgram)


class AttractionAnswerGeneratorTests(unittest.IsolatedAsyncioTestCase):
    def _candidates(self):
        return [
            SearchCandidate(
                domain="attraction",
                place_id=str(index),
                task_id="task_1",
                name=f"후보 {index}",
                category="관광지",
                base_score=1 - index / 10,
                final_score=1 - index / 10,
                attributes={"kind": "attraction"},
            )
            for index in range(1, 5)
        ]

    async def _generate(self, generator):
        return await generator.generate(
            question="경복궁 근처 추천해줘",
            language="ko",
            location="경복궁",
            themes=["역사"],
            candidates=self._candidates(),
        )

    async def test_valid_prediction_returns_model_selection(self):
        class Program:
            def __call__(self, **inputs):
                return SimpleNamespace(
                    selected_place_ids=["2", "1", "3"],
                    selection_reasons_json=(
                        '{"2":"근거 2","1":"근거 1","3":"근거 3"}'
                    ),
                    answer="경복궁 근처 추천 결과입니다.",
                )

        result = await self._generate(
            AttractionAnswerGenerator(
                program_loader=lambda: Program(),
                lm_factory=lambda: None,
            )
        )

        self.assertFalse(result.used_fallback)
        self.assertEqual([item.place_id for item in result.selections], ["2", "1", "3"])

    async def test_model_or_artifact_error_returns_ranked_fallback(self):
        class BrokenProgram:
            def __call__(self, **inputs):
                raise RuntimeError("model failed")

        generators = [
            AttractionAnswerGenerator(
                program_loader=lambda: BrokenProgram(),
                lm_factory=lambda: None,
            ),
            AttractionAnswerGenerator(
                program_loader=lambda: (_ for _ in ()).throw(
                    FileNotFoundError("artifact missing")
                ),
                lm_factory=lambda: None,
            ),
        ]

        for generator in generators:
            with self.subTest(generator=generator):
                result = await self._generate(generator)
                self.assertTrue(result.used_fallback)
                self.assertEqual(
                    [item.place_id for item in result.selections], ["1", "2", "3"]
                )

    async def test_timeout_returns_ranked_fallback(self):
        class SlowProgram:
            def __call__(self, **inputs):
                time.sleep(0.05)
                raise AssertionError("late result must be ignored")

        result = await self._generate(
            AttractionAnswerGenerator(
                program_loader=lambda: SlowProgram(),
                lm_factory=lambda: None,
                timeout_seconds=0.01,
            )
        )

        self.assertTrue(result.used_fallback)
        self.assertEqual([item.place_id for item in result.selections], ["1", "2", "3"])


class AttractionRecommendationPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_reuses_common_attraction_selection_service(self):
        candidate = SearchCandidate(
            domain="attraction",
            place_id="palace-1",
            task_id="task_1",
            name="경복궁",
            category="역사관광",
            base_score=0.8,
            final_score=0.9,
        )

        class Search:
            async def search(self, request):
                return [candidate]

        class SelectionService:
            def __init__(self):
                self.calls = []

            async def select(self, request, candidates):
                self.calls.append((request, candidates))
                return CandidateSelectionResult(
                    answer="경복궁을 추천합니다.",
                    selections=[CandidateSelection(
                        place_id="palace-1",
                        selection_reason="질문과 잘 맞습니다.",
                    )],
                )

        selection_service = SelectionService()
        pipeline = AttractionRecommendationPipeline(
            search_service=Search(),
            congestion_reranker=None,
            selection_service=selection_service,
        )
        request = DomainSearchRequest(
            task_id="task_1",
            domain="attraction",
            search_query="경복궁 근처 관광지",
        )

        result = await pipeline.recommend(request)

        self.assertEqual(1, len(selection_service.calls))
        called_request, called_candidates = selection_service.calls[0]
        self.assertIs(request, called_request)
        self.assertEqual(["palace-1"], [item.place_id for item in called_candidates])
        self.assertEqual("경복궁을 추천합니다.", result.answer.answer)
        self.assertEqual(["palace-1"], [item.place_id for item in result.candidates])

    async def test_pipeline_orders_search_congestion_then_answer(self):
        calls = []
        candidates = [
            SearchCandidate(
                domain="attraction",
                place_id=str(index),
                task_id="task_1",
                name=f"후보 {index}",
                category="관광지",
                base_score=score,
                final_score=score,
                attributes={"kind": "attraction"},
            )
            for index, score in ((1, 0.5), (2, 0.9), (3, 0.7))
        ]

        class Search:
            async def search(self, request):
                calls.append("search")
                return candidates

        class Congestion:
            async def rerank(self, values, question, *, language):
                calls.append(("congestion", [item.place_id for item in values]))
                return values

        class Answer:
            async def generate(self, **values):
                calls.append(("answer", [item.place_id for item in values["candidates"]]))
                return AttractionAnswerResult(
                    answer="result",
                    selections=[
                        AttractionSelection(
                            place_id="3",
                            selection_reason="third",
                        ),
                        AttractionSelection(
                            place_id="2",
                            selection_reason="second",
                        ),
                    ],
                )

        pipeline = AttractionRecommendationPipeline(
            search_service=Search(),
            congestion_reranker=Congestion(),
            answer_generator=Answer(),
        )
        result = await pipeline.recommend(
            DomainSearchRequest(
                task_id="task_1",
                domain="attraction",
                language="ko",
                search_query="경복궁",
                location="경복궁",
                themes=["역사"],
            ),
            use_congestion=True,
        )

        self.assertEqual(result.answer.answer, "result")
        self.assertEqual(
            [candidate.place_id for candidate in result.candidates],
            ["3", "2"],
        )
        self.assertEqual(calls[0], "search")
        self.assertEqual(calls[1], ("congestion", ["2", "3", "1"]))
        self.assertEqual(calls[2], ("answer", ["2", "3", "1"]))

    async def test_pipeline_skips_congestion_when_policy_disables_it(self):
        calls = []
        candidate = SearchCandidate(
            domain="attraction",
            place_id="1",
            task_id="task_1",
            name="후보 1",
            category="관광지",
            base_score=0.9,
            final_score=0.9,
            attributes={"kind": "attraction"},
        )

        class Search:
            async def search(self, request):
                return [candidate]

        class Congestion:
            async def rerank(self, *args, **kwargs):
                calls.append("congestion")
                return args[0]

        class Answer:
            async def generate(self, **values):
                return AttractionAnswerResult(
                    answer="result",
                    selections=[AttractionSelection(
                        place_id="1",
                        selection_reason="reason",
                    )],
                )

        pipeline = AttractionRecommendationPipeline(
            search_service=Search(),
            congestion_reranker=Congestion(),
            answer_generator=Answer(),
        )

        await pipeline.recommend(
            DomainSearchRequest(
                task_id="task_1",
                domain="attraction",
                search_query="서울 관광지",
            ),
            use_congestion=False,
        )

        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
