"""Compare the legacy single DSPy artifact with split production artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

import dspy

from core.config import settings
from domains.attraction.answer_program import load_attraction_program
from domains.attraction.dspy.service import load_split_attraction_runtime
from domains.attraction.dspy.validator import validate_selection_prediction
from experiments.attraction_dspy.production_dataset import (
    ProductionDspyCase,
    load_production_splits,
    to_selection_example,
)


def build_comparison_plan(data_dir: str | Path) -> dict:
    return {
        "splits": {
            "test": len(load_production_splits(data_dir, "selection")["test"]),
            "gold_test": len(load_production_splits(data_dir, "gold_test")["test"]),
        },
        "methods": {"legacy_single": 1, "split": 2},
    }


def evaluate_cases(cases: list[ProductionDspyCase], *, source_split: str, candidate_artifact_dir: Path | None = None) -> list[dict]:
    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")
    lm = dspy.LM(settings.attraction_dspy_model, api_key=api_key,
                 temperature=settings.attraction_dspy_temperature,
                 max_tokens=settings.attraction_dspy_max_tokens)
    legacy = load_attraction_program()
    split = (
        load_split_attraction_runtime(
            candidate_artifact_dir / "selection_v1.json",
            candidate_artifact_dir / "answer_v1.json",
        )
        if candidate_artifact_dir else load_split_attraction_runtime()
    )
    rows = []
    for case in cases:
        rows.append(_legacy_row(case, legacy, lm, source_split))
        rows.append(_split_row(case, split, source_split))
    return rows


def _legacy_row(case, program, lm, source_split) -> dict:
    started = perf_counter()
    try:
        example = to_selection_example(case)
        with dspy.context(lm=lm):
            prediction = program(**{name: getattr(example, name) for name in example.inputs()})
        selection = validate_selection_prediction(case.answer_input, {
            "selected_place_ids": prediction.selected_place_ids,
            "forbidden_place_ids": [],
            "selection_reasons": json.loads(prediction.selection_reasons_json),
        })
        return _row(case, "legacy_single", selection.selected_place_ids,
                    str(getattr(prediction, "answer", "")), perf_counter() - started,
                    source_split=source_split)
    except Exception as error:
        return _row(case, "legacy_single", [], "", perf_counter() - started, error, source_split)


def _split_row(case, runtime, source_split) -> dict:
    started = perf_counter()
    try:
        result = runtime.run(case.answer_input)
        return _row(case, "split", [item.place_id for item in result.selections],
                    result.answer, perf_counter() - started, source_split=source_split)
    except Exception as error:
        return _row(case, "split", [], "", perf_counter() - started, error, source_split)


def _row(case, method, selected_ids, answer, elapsed, error=None, source_split=None) -> dict:
    expected = case.selected_place_ids
    return {
        "case_id": case.case_id, "source_split": source_split, "method": method,
        "selected_place_ids": selected_ids, "expected_place_ids": expected,
        "selection_exact": selected_ids == expected,
        "selection_jaccard": _jaccard(selected_ids, expected),
        "answer": answer, "elapsed_seconds": elapsed,
        "error": f"{type(error).__name__}: {error}" if error else None,
    }


def _jaccard(actual, expected) -> float:
    actual, expected = set(actual), set(expected)
    return 1.0 if not actual and not expected else len(actual & expected) / len(actual | expected)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).parents[2] / "data" / "attraction" / "DSPy")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results" / "production_comparison.jsonl")
    parser.add_argument("--candidate-artifact-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    plan = build_comparison_plan(args.data_dir)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0
    selection = load_production_splits(args.data_dir, "selection")["test"]
    gold = load_production_splits(args.data_dir, "gold_test")["test"]
    rows = evaluate_cases(selection, source_split="test", candidate_artifact_dir=args.candidate_artifact_dir)
    rows.extend(evaluate_cases(gold, source_split="gold_test", candidate_artifact_dir=args.candidate_artifact_dir))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
