"""MIPROv2를 이용한 관광 DSPy 오프라인 최적화 CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

import dspy

from core.config import settings
from domains.attraction.answer_program import AttractionSelectionAnswerProgram
from domains.attraction.dspy.programs import (
    TourismAnswerProgram,
    TourismSelectionProgram,
)
from experiments.attraction_dspy.dataset import load_dataset_splits, to_dspy_example
from experiments.attraction_dspy.evaluate import dataset_fingerprint
from experiments.attraction_dspy.metrics import build_optimization_metric
from experiments.attraction_dspy.production_dataset import (
    load_production_splits,
    to_answer_example,
    to_selection_example,
)
from experiments.attraction_dspy.production_metrics import (
    build_answer_metric,
    build_selection_metric,
)
from experiments.attraction_dspy.run_budget import (
    estimate_run_budget,
    require_within_budget,
)


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


def build_production_optimization_plan(
    data_dir: str | Path,
    *,
    num_trials: int = 3,
    max_cost_usd: float = 0.50,
) -> dict:
    """Describe separate, leakage-safe optimization runs without calling an LLM."""

    programs = {}
    for kind in ("selection", "answer"):
        splits = load_production_splits(data_dir, kind)
        train_ids = {case.case_id for case in splits["train"]}
        dev_ids = {case.case_id for case in splits["dev"]}
        test_ids = {case.case_id for case in splits["test"]}
        if train_ids & dev_ids or train_ids & test_ids or dev_ids & test_ids:
            raise ValueError(f"{kind} DSPy split 간 example_id가 중복됩니다.")
        programs[kind] = {
            "train_split": "train",
            "validation_split": "dev",
            "evaluation_split": "test",
            "train_cases": len(train_ids),
            "dev_cases": len(dev_ids),
            "test_cases": len(test_ids),
            "optimizer": "MIPROv2",
            "num_trials": num_trials,
        }
    budget = estimate_run_budget(
        Path(data_dir), num_trials=num_trials, include_full_evaluation=False,
    )
    require_within_budget(budget, max_cost_usd)
    return {
        "programs": programs,
        "gold_test_policy": "evaluation_only",
        "budget": budget,
        "max_cost_usd": max_cost_usd,
    }


def pending_production_programs(artifact_dir: Path) -> tuple[str, ...]:
    """Return candidate programs that have not already been exported."""
    return tuple(
        kind for kind in ("selection", "answer")
        if not (artifact_dir / f"{kind}_v1.json").is_file()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).parents[2] / "data" / "attraction" / "DSPy",
    )
    parser.add_argument("--artifact", type=Path, default=settings.attraction_dspy_artifact_path)
    parser.add_argument("--run-production", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--artifact-dir", type=Path,
        help="후보 selection/answer artifact와 metadata를 저장할 디렉터리",
    )
    parser.add_argument("--num-trials", type=int, default=3)
    parser.add_argument("--max-cost-usd", type=float, default=0.50)
    args = parser.parse_args(argv)
    production_plan = build_production_optimization_plan(
        args.data_dir,
        num_trials=args.num_trials,
        max_cost_usd=args.max_cost_usd,
    )
    print(json.dumps(production_plan, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0

    if args.run_production:
        _compile_production_programs(
            args.data_dir,
            artifact_dir=args.artifact_dir,
            num_trials=args.num_trials,
            max_cost_usd=args.max_cost_usd,
        )
        return 0

    splits = load_dataset_splits(args.data_dir, allow_provisional=True)
    plan = build_optimization_plan(splits)
    print(json.dumps(plan, ensure_ascii=False, indent=2))

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


def _compile_production_programs(
    data_dir: Path,
    *,
    artifact_dir: Path | None = None,
    num_trials: int = 3,
    max_cost_usd: float = 0.50,
) -> None:
    """Compile and export both programs; this path intentionally requires an API key."""

    if artifact_dir is None:
        raise ValueError("운영 artifact 보호를 위해 --artifact-dir가 필요합니다.")
    if artifact_dir.resolve() == settings.attraction_dspy_selection_artifact_path.parent.resolve():
        raise ValueError("운영 artifact 디렉터리에는 candidate를 저장할 수 없습니다.")
    budget = estimate_run_budget(
        data_dir, num_trials=num_trials, include_full_evaluation=False,
    )
    require_within_budget(budget, max_cost_usd)
    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")
    targets = (
        (
            "selection",
            TourismSelectionProgram,
            to_selection_example,
            build_selection_metric,
            artifact_dir / "selection_v1.json",
        ),
        (
            "answer",
            TourismAnswerProgram,
            to_answer_example,
            build_answer_metric,
            artifact_dir / "answer_v1.json",
        ),
    )
    pending = set(pending_production_programs(artifact_dir))
    metadata: dict[str, object] = {
        "dspy_version": dspy.__version__,
        "model": settings.attraction_dspy_model,
        "temperature": settings.attraction_dspy_temperature,
        "max_tokens": settings.attraction_dspy_max_tokens,
        "num_trials": num_trials,
        "budget": budget,
        "resumed_existing_programs": [
            kind for kind in ("selection", "answer") if kind not in pending
        ],
        "programs": {},
    }
    for kind, program_type, example_factory, metric_factory, artifact_path in targets:
        if kind not in pending:
            continue
        lm = dspy.LM(
            settings.attraction_dspy_model,
            api_key=api_key,
            temperature=settings.attraction_dspy_temperature,
            max_tokens=settings.attraction_dspy_max_tokens,
        )
        splits = load_production_splits(data_dir, kind)
        # Keep labels outside Example inputs; the metric closure resolves them by case_id.
        metric = metric_factory(
            {case.case_id: case for split in splits.values() for case in split}
        )
        optimizer = dspy.MIPROv2(
            metric=metric,
            prompt_model=lm,
            task_model=lm,
            auto=None,
            num_candidates=4,
            num_threads=1,
            max_bootstrapped_demos=0,
            max_labeled_demos=0,
            seed=42,
        )
        started = perf_counter()
        with dspy.context(lm=lm):
            optimized = optimizer.compile(
                program_type(),
                trainset=[example_factory(case) for case in splits["train"]],
                valset=[example_factory(case) for case in splits["dev"]],
                num_trials=num_trials,
                minibatch=False,
                max_bootstrapped_demos=0,
                max_labeled_demos=0,
                seed=42,
                requires_permission_to_run=False,
            )
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        optimized.save(str(artifact_path))
        metadata["programs"][kind] = {
            "train_cases": len(splits["train"]),
            "dev_cases": len(splits["dev"]),
            "test_cases": len(splits["test"]),
            "artifact": str(artifact_path),
            "max_tokens": max_tokens,
            "elapsed_seconds": perf_counter() - started,
        }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
