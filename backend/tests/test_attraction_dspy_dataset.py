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
from experiments.attraction_dspy.optimize import (
    build_production_optimization_plan,
    pending_production_programs,
)
from experiments.attraction_dspy.production_evaluate import summarize_candidate
from domains.attraction.dspy.signatures import TourismAnswerSignature
from experiments.attraction_dspy.run_budget import (
    estimate_run_budget,
    require_within_budget,
)
from experiments.attraction_dspy.production_dataset import (
    adapt_production_example,
    load_production_splits,
    to_answer_example,
    to_reason_example,
    to_selection_example,
)
from experiments.attraction_dspy.production_metrics import (
    build_answer_metric,
    build_reason_metric,
    build_selection_metric,
)
from experiments.attraction_dspy.build_augmentation_draft import build_augmentation_draft
from experiments.attraction_dspy.review_augmentation_draft import source_cid_matches_place_id


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
    def test_db_source_cid_match_accepts_prefixed_attraction_ids(self):
        self.assertTrue(source_cid_matches_place_id("KOPbo1j5m", "bo1j5m"))
        self.assertTrue(source_cid_matches_place_id("bo1j5m", "bo1j5m"))
        self.assertFalse(source_cid_matches_place_id("KOPbo1j5m", "different"))

    def test_augmentation_draft_is_disjoint_from_existing_splits_and_gold(self):
        dataset_root = Path(__file__).parents[1] / "data" / "attraction" / "DSPy"
        rows = build_augmentation_draft(dataset_root)

        self.assertEqual(32, len(rows))
        self.assertEqual({"pending"}, {row["review_status"] for row in rows})
        self.assertEqual({"train", "dev"}, {row["metadata"]["target_split"] for row in rows})

        used_place_ids = set()
        used_groups = set()
        for kind in ("selection", "answer", "exception", "gold_test"):
            paths = ([dataset_root / "gold_test" / "gold_test.jsonl"] if kind == "gold_test"
                     else [dataset_root / kind / f"{split}.jsonl" for split in ("train", "dev", "test")])
            for path in paths:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    used_place_ids.update(row.get("metadata", {}).get("source_place_cids", []))
                    used_groups.add(row.get("metadata", {}).get("split_group"))

        draft_place_ids = {cid for row in rows for cid in row["metadata"]["source_place_cids"]}
        draft_groups = {row["metadata"]["split_group"] for row in rows}
        self.assertFalse(used_place_ids.intersection(draft_place_ids))
        self.assertFalse(used_groups.intersection(draft_groups))

    def test_production_example_adapter_uses_attraction_answer_input_contract(self):
        adapted = adapt_production_example(
            {
                "example_id": "selection-ko-1",
                "input": {
                    "question": "전시 추천",
                    "language": "ko",
                    "location": "서울",
                    "themes": ["전시"],
                    "candidates": [{
                        "place_id": "p1", "rank": 1, "name": "전시장",
                        "category": "전시", "congestion": None, "weather": None,
                    }],
                },
                "expected": {
                    "selected_place_ids": ["p1"],
                    "forbidden_place_ids": [],
                    "selection_reasons": {"p1": "근거"},
                },
            }
        )

        self.assertEqual("selection-ko-1", adapted.case_id)
        self.assertEqual("p1", adapted.answer_input.candidates[0].place_id)
        self.assertEqual("unavailable", adapted.answer_input.candidates[0].congestion.status)
        self.assertEqual(["p1"], adapted.selected_place_ids)
        self.assertEqual(
            set(to_selection_example(adapted).inputs()),
            {"language", "question", "location", "themes_json", "selection_count", "candidates_json"},
        )
        self.assertEqual(
            set(to_answer_example(adapted).inputs()),
            {"language", "question", "selected_candidates_json", "selection_reasons_json"},
        )
        self.assertEqual(
            set(to_reason_example(adapted).inputs()),
            {"language", "question", "selected_candidates_json", "selection_reasons_json"},
        )

    def test_production_split_loader_keeps_gold_out_of_training_splits(self):
        dataset_root = Path(__file__).parents[1] / "data" / "attraction" / "DSPy"
        splits = load_production_splits(dataset_root, "selection")

        self.assertEqual(set(splits), {"train", "dev", "test"})
        self.assertTrue(splits["train"])
        self.assertTrue(splits["dev"])
        self.assertTrue(splits["test"])
        self.assertTrue(all(case.case_id not in {
            gold.case_id
            for gold in load_production_splits(dataset_root, "gold_test")["test"]
        } for case in splits["train"]))

    def test_production_optimization_plan_has_separate_programs(self):
        dataset_root = Path(__file__).parents[1] / "data" / "attraction" / "DSPy"
        plan = build_production_optimization_plan(dataset_root)

        self.assertEqual(set(plan["programs"]), {"selection", "answer"})
        self.assertEqual(plan["programs"]["selection"]["train_split"], "train")
        self.assertEqual(plan["programs"]["answer"]["validation_split"], "dev")
        self.assertNotIn("gold_test", plan["programs"]["selection"])

    def test_production_plan_uses_requested_trial_count_and_budget(self):
        dataset_root = Path(__file__).parents[1] / "data" / "attraction" / "DSPy" / "optimization_v2"

        plan = build_production_optimization_plan(
            dataset_root, num_trials=1, max_cost_usd=0.10,
        )

        self.assertEqual(1, plan["programs"]["selection"]["num_trials"])
        self.assertEqual(1, plan["programs"]["answer"]["num_trials"])
        self.assertEqual(0.10, plan["max_cost_usd"])
        self.assertEqual(104, plan["budget"]["optimization_calls"])

    def test_resume_only_runs_missing_candidate_artifact(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            artifact_dir = Path(temp_directory)
            (artifact_dir / "selection_v1.json").write_text("{}", encoding="utf-8")

            self.assertEqual(("answer",), pending_production_programs(artifact_dir))

    def test_budget_estimate_covers_pilot_and_full_candidate_evaluation(self):
        dataset_root = Path(__file__).parents[1] / "data" / "attraction" / "DSPy" / "optimization_v2"

        pilot = estimate_run_budget(
            dataset_root, num_trials=1, include_full_evaluation=False,
        )
        full = estimate_run_budget(
            dataset_root, num_trials=3, include_full_evaluation=True,
        )

        self.assertEqual(104, pilot["optimization_calls"])
        self.assertEqual(0, pilot["evaluation_calls"])
        self.assertEqual(248, full["optimization_calls"])
        self.assertEqual(270, full["evaluation_calls"])
        self.assertEqual(518, full["total_calls"])
        self.assertEqual(124_800, pilot["output_token_cap"])
        self.assertGreater(full["estimated_cost_usd"], 0)

    def test_budget_guard_rejects_over_cap(self):
        with self.assertRaisesRegex(ValueError, "비용 상한"):
            require_within_budget({"estimated_cost_usd": 0.51}, 0.50)

    def test_candidate_summary_requires_zero_failures_low_fallback_and_legacy_accuracy(self):
        summary = summarize_candidate([
            {"source_split": "test", "method": "legacy_single", "selection_exact": True, "fallback_used": False, "hard_failure": False},
            {"source_split": "test", "method": "split", "selection_exact": True, "fallback_used": False, "hard_failure": False},
            {"source_split": "gold_test", "method": "legacy_single", "selection_exact": True, "fallback_used": False, "hard_failure": False},
            {"source_split": "gold_test", "method": "split", "selection_exact": True, "fallback_used": False, "hard_failure": False},
        ])

        self.assertEqual(0, summary["hard_failures"])
        self.assertEqual(0.0, summary["fallback_rate"])
        self.assertTrue(summary["accepted"])

    def test_candidate_summary_rejects_projected_fallback_above_five_percent(self):
        summary = summarize_candidate([
            {"source_split": "test", "method": "legacy_single", "selection_exact": True, "fallback_used": False, "hard_failure": False},
            {"source_split": "test", "method": "split", "selection_exact": True, "fallback_used": True, "hard_failure": True},
        ])

        self.assertFalse(summary["accepted"])

    def test_answer_signature_requires_verbatim_candidate_evidence(self):
        self.assertIn("verbatim", TourismAnswerSignature.__doc__.casefold())
        self.assertIn("never summarize", TourismAnswerSignature.__doc__.casefold())
        self.assertIn("at most one", TourismAnswerSignature.__doc__.casefold())

    def test_production_metrics_reject_invalid_outputs_and_reward_gold_ids(self):
        case = adapt_production_example(
            {
                "example_id": "answer-ko-1",
                "input": {
                    "question": "전시 추천", "language": "ko", "candidates": [{
                        "place_id": "p1", "rank": 1, "name": "전시장", "category": "전시",
                    }],
                },
                "expected": {
                    "selected_place_ids": ["p1"],
                    "selection_reasons": {"p1": "전시 근거"},
                    "structured_answer": {
                        "language": "ko", "recommendations": [{
                            "place_id": "p1", "name": "전시장", "recommendation_reason": "전시 관람에 좋습니다.",
                            "congestion": {"status": "unavailable"}, "weather": {"status": "unavailable"},
                        }], "no_result_reason": None,
                    },
                },
            }
        )
        example = to_selection_example(case)
        selection_metric = build_selection_metric({case.case_id: case})
        self.assertEqual(1.0, selection_metric(example, SimpleNamespace(
            selected_place_ids=["p1"], forbidden_place_ids=[],
            selection_reasons_json=json.dumps({"p1": "전시 근거"}),
        )))
        self.assertEqual(0.0, selection_metric(example, SimpleNamespace(
            selected_place_ids=["other"], forbidden_place_ids=[],
            selection_reasons_json=json.dumps({"other": "근거"}),
        )))

        answer_metric = build_answer_metric({case.case_id: case})
        self.assertEqual(1.0, answer_metric(to_answer_example(case), SimpleNamespace(
            structured_answer_json=json.dumps(case.structured_answer, ensure_ascii=False),
        )))

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
