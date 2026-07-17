import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from experiments.attraction_dspy.dataset import (
    AttractionDspyCase,
    DatasetIntegrityError,
    load_dataset_splits,
    to_dspy_example,
)
from experiments.attraction_dspy.metrics import (
    AttractionPrivateJudgeSignature,
    build_optimization_metric,
    evaluate_attraction_prediction,
)
from experiments.attraction_dspy.evaluate import build_evaluation_plan
from experiments.attraction_dspy.optimize import build_optimization_plan


def case_payload(case_id: str, *, language: str = "ko") -> dict:
    return {
        "case_id": case_id,
        "source": {
            "type": "notebook",
            "reference": "Tourism_Agent_DSPy_Prompt_Optimization.ipynb",
            "source_case_id": case_id,
        },
        "public_input": {
            "question": "경복궁 근처 관광지 추천",
            "language": language,
            "location": "경복궁",
            "themes": ["역사"],
            "selection_count": 3,
            "candidates": [
                {
                    "place_id": str(index),
                    "rank": index,
                    "name": f"후보 {index}",
                    "category": "고궁",
                    "description": f"조선 역사 근거 {index}",
                    "reviews": [f"역사 산책 리뷰 {index}"],
                    "congestion": None,
                }
                for index in range(1, 6)
            ],
        },
        "private_label": {
            "acceptable_place_ids": ["1", "2", "3"],
            "required_conditions": ["역사"],
            "forbidden_claims": ["무료 입장"],
            "reference_answer": "후보 1, 2, 3을 추천합니다.",
            "human_review_status": "reviewed",
        },
    }


class AttractionDspyDatasetTests(unittest.TestCase):
    def _write_split(self, directory: Path, split: str, rows: list[dict]):
        (directory / f"{split}.jsonl").write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )

    def test_loader_keeps_splits_disjoint_and_requires_reviewed_labels(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            directory = Path(temp_directory)
            for split in ("train", "dev", "test", "blind"):
                self._write_split(directory, split, [case_payload(f"{split}_1")])

            splits = load_dataset_splits(
                directory,
                expected_counts={split: 1 for split in ("train", "dev", "test", "blind")},
            )

            self.assertEqual(set(splits), {"train", "dev", "test", "blind"})

            self._write_split(directory, "blind", [case_payload("train_1")])
            with self.assertRaises(DatasetIntegrityError):
                load_dataset_splits(
                    directory,
                    expected_counts={split: 1 for split in ("train", "dev", "test", "blind")},
                )

            unreviewed = case_payload("blind_1")
            unreviewed["private_label"]["human_review_status"] = "needs_review"
            self._write_split(directory, "blind", [unreviewed])
            with self.assertRaises(DatasetIntegrityError):
                load_dataset_splits(
                    directory,
                    expected_counts={split: 1 for split in ("train", "dev", "test", "blind")},
                )

    def test_dspy_example_contains_only_public_inputs(self):
        case = AttractionDspyCase.model_validate(case_payload("train_1"))

        example = to_dspy_example(case)
        serialized = dict(example)

        self.assertEqual(
            set(example.inputs()),
            {
                "language",
                "question",
                "location",
                "themes_json",
                "selection_count",
                "candidates_json",
            },
        )
        self.assertNotIn("private_label", serialized)
        self.assertNotIn("reference_answer", serialized)
        self.assertNotIn("acceptable_place_ids", serialized)

    def test_evaluation_and_optimization_dry_run_plans_are_cost_free(self):
        splits = {
            split: [AttractionDspyCase.model_validate(case_payload(f"{split}_1"))]
            for split in ("train", "dev", "test", "blind")
        }

        evaluation = build_evaluation_plan(
            splits,
            split="test",
            methods=("manual", "dspy_baseline"),
        )
        optimization = build_optimization_plan(splits)

        self.assertEqual(evaluation["cases"], 1)
        self.assertEqual(evaluation["methods"], 2)
        self.assertEqual(len(evaluation["dataset_fingerprint"]), 64)
        self.assertEqual(optimization["train_cases"], 1)
        self.assertEqual(optimization["dev_cases"], 1)
        self.assertEqual(optimization["num_candidates"], 4)
        self.assertEqual(optimization["num_trials"], 3)
        self.assertIsNone(optimization["auto"])
        self.assertFalse(optimization["minibatch"])
        self.assertEqual(optimization["seed"], 42)


class AttractionHybridMetricTests(unittest.TestCase):
    def _prediction(self, **overrides):
        values = {
            "selected_place_ids": ["1", "2", "3"],
            "selection_reasons_json": json.dumps(
                {
                    "1": "조선 역사 근거",
                    "2": "조선 역사 근거",
                    "3": "조선 역사 근거",
                },
                ensure_ascii=False,
            ),
            "answer": "조선 역사를 살펴볼 수 있는 세 곳을 추천합니다.",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_component_weights_and_hybrid_ratio(self):
        case = AttractionDspyCase.model_validate(case_payload("test_1"))

        result = evaluate_attraction_prediction(
            case,
            self._prediction(),
            judge_score=0.5,
        )

        self.assertEqual(
            result.component_weights,
            {
                "selection": 0.40,
                "grounding": 0.25,
                "conditions": 0.15,
                "language_structure": 0.10,
                "clarity": 0.10,
            },
        )
        self.assertAlmostEqual(
            result.score,
            0.40 * result.rule_score + 0.60 * 0.5,
        )

    def test_hard_fail_conditions_return_zero(self):
        case = AttractionDspyCase.model_validate(case_payload("test_1"))
        invalid_predictions = [
            self._prediction(selected_place_ids=["unknown", "2", "3"]),
            self._prediction(selected_place_ids=["1", "1", "2"]),
            self._prediction(answer="This answer is in the wrong language."),
            self._prediction(answer="무료 입장이며 한적한 곳입니다."),
        ]

        for invalid in invalid_predictions:
            with self.subTest(prediction=invalid):
                result = evaluate_attraction_prediction(
                    case,
                    invalid,
                    judge_score=1.0,
                )
                self.assertTrue(result.hard_fail)
                self.assertEqual(result.score, 0.0)

    def test_reference_answer_is_not_sent_to_private_judge(self):
        case = AttractionDspyCase.model_validate(case_payload("test_1"))
        captured = {}

        def judge(**inputs):
            captured.update(inputs)
            return SimpleNamespace(score=4, hard_fail=False, reason="grounded")

        evaluate_attraction_prediction(case, self._prediction(), judge=judge)

        self.assertNotIn("reference_answer", captured)
        self.assertNotIn("private_label", captured)
        self.assertIn("candidates_json", captured)

    def test_private_judge_and_optimizer_metric_keep_labels_out_of_inputs(self):
        self.assertNotIn(
            "reference_answer",
            AttractionPrivateJudgeSignature.input_fields,
        )
        self.assertNotIn(
            "private_label",
            AttractionPrivateJudgeSignature.input_fields,
        )
        case = AttractionDspyCase.model_validate(case_payload("train_1"))
        example = to_dspy_example(case)
        judge = lambda **inputs: SimpleNamespace(
            score=5,
            hard_fail=False,
            reason="grounded",
        )
        metric = build_optimization_metric({case.case_id: case}, judge=judge)

        score = metric(example, self._prediction())

        self.assertGreater(score, 0.0)


if __name__ == "__main__":
    unittest.main()
