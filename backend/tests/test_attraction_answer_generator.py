import time
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from domains.attraction import AttractionAnswerGenerator
from domains.common.models import SearchCandidate
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


if __name__ == "__main__":
    unittest.main()
