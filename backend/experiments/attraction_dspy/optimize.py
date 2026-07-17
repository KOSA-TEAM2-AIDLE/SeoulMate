"""MIPROv2를 이용한 관광 DSPy 오프라인 최적화 CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

import dspy

from core.config import settings
from domains.attraction.answer_program import AttractionSelectionAnswerProgram
from experiments.attraction_dspy.dataset import load_dataset_splits, to_dspy_example
from experiments.attraction_dspy.evaluate import dataset_fingerprint
from experiments.attraction_dspy.metrics import build_optimization_metric


def build_optimization_plan(splits) -> dict:
    train_ids = {case.case_id for case in splits["train"]}
    dev_ids = {case.case_id for case in splits["dev"]}
    held_out_ids = {
        case.case_id for split in ("test", "blind") for case in splits[split]
    }
    if (train_ids | dev_ids) & held_out_ids:
        raise ValueError("Train/Dev와 Test/Blind ID가 교차합니다.")
    return {
        "train_cases": len(train_ids),
        "dev_cases": len(dev_ids),
        "test_cases": len(splits["test"]),
        "blind_cases": len(splits["blind"]),
        "num_candidates": 4,
        "num_trials": 3,
        "auto": None,
        "minibatch": False,
        "max_bootstrapped_demos": 0,
        "max_labeled_demos": 0,
        "num_threads": 1,
        "seed": 42,
        "dataset_fingerprint": dataset_fingerprint(splits),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).parent / "data")
    parser.add_argument("--artifact", type=Path, default=settings.attraction_dspy_artifact_path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    splits = load_dataset_splits(args.data_dir, allow_provisional=True)
    plan = build_optimization_plan(splits)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0

    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")
    lm = dspy.LM(
        settings.attraction_dspy_model,
        api_key=api_key,
        temperature=settings.attraction_dspy_temperature,
        max_tokens=settings.attraction_dspy_max_tokens,
    )
    case_index = {case.case_id: case for split in splits.values() for case in split}
    metric = build_optimization_metric(case_index)
    optimizer = dspy.MIPROv2(
        metric=metric,
        auto=plan["auto"],
        prompt_model=lm,
        task_model=lm,
        num_candidates=plan["num_candidates"],
        num_threads=plan["num_threads"],
        max_bootstrapped_demos=0,
        max_labeled_demos=0,
        seed=plan["seed"],
    )
    started = perf_counter()
    with dspy.context(lm=lm):
        optimized = optimizer.compile(
            AttractionSelectionAnswerProgram(),
            trainset=[to_dspy_example(case) for case in splits["train"]],
            valset=[to_dspy_example(case) for case in splits["dev"]],
            num_trials=plan["num_trials"],
            minibatch=plan["minibatch"],
            max_bootstrapped_demos=0,
            max_labeled_demos=0,
            seed=plan["seed"],
            requires_permission_to_run=False,
        )
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    optimized.save(str(args.artifact))
    metadata = {
        **plan,
        "dspy_version": dspy.__version__,
        "model": settings.attraction_dspy_model,
        "temperature": settings.attraction_dspy_temperature,
        "max_tokens": settings.attraction_dspy_max_tokens,
        "elapsed_seconds": perf_counter() - started,
    }
    args.artifact.with_name("optimization_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
