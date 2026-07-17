"""Manual·DSPy baseline·optimized 비교를 위한 오프라인 runner."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import dspy

from core.config import settings
from domains.attraction.answer_program import (
    AttractionSelectionAnswerProgram,
    load_attraction_program,
)
from experiments.attraction_dspy.dataset import (
    AttractionDspyCase,
    load_dataset_splits,
    to_dspy_example,
)


METHODS = ("manual", "dspy_baseline", "dspy_optimized")


def dataset_fingerprint(splits: dict[str, list[AttractionDspyCase]]) -> str:
    payload = [
        case.model_dump(mode="json")
        for split in sorted(splits)
        for case in splits[split]
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_evaluation_plan(
    splits: dict[str, list[AttractionDspyCase]],
    *,
    split: str,
    methods: tuple[str, ...],
) -> dict:
    if split not in splits:
        raise ValueError(f"등록되지 않은 split입니다: {split}")
    unknown = set(methods) - set(METHODS)
    if unknown:
        raise ValueError(f"등록되지 않은 평가 방식입니다: {sorted(unknown)}")
    return {
        "split": split,
        "cases": len(splits[split]),
        "methods": len(methods),
        "method_names": list(methods),
        "api_calls": len(splits[split]) * len(methods),
        "dataset_fingerprint": dataset_fingerprint(splits),
    }


def _program_for(method: str):
    if method == "dspy_optimized":
        return load_attraction_program()
    # manual은 Task 9의 명시적 고정 Signature 기준선이고,
    # dspy_baseline은 아직 최적화되지 않은 동일 Program 구조를 사용한다.
    return AttractionSelectionAnswerProgram()


def run_evaluation(
    cases: list[AttractionDspyCase],
    *,
    methods: tuple[str, ...],
) -> list[dict]:
    rows = []
    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 필요합니다.")
    lm = dspy.LM(
        settings.attraction_dspy_model,
        api_key=api_key,
        temperature=settings.attraction_dspy_temperature,
        max_tokens=settings.attraction_dspy_max_tokens,
    )
    for method in methods:
        program = _program_for(method)
        for case in cases:
            example = to_dspy_example(case)
            inputs = {name: getattr(example, name) for name in example.inputs()}
            started = perf_counter()
            try:
                with dspy.context(lm=lm):
                    prediction = program(**inputs)
                error = None
                selected = list(getattr(prediction, "selected_place_ids", []) or [])
                reasons = str(getattr(prediction, "selection_reasons_json", "") or "")
                answer = str(getattr(prediction, "answer", "") or "")
            except Exception as exception:
                selected, reasons, answer = [], "", ""
                error = f"{type(exception).__name__}: {exception}"
            rows.append(
                {
                    "case_id": case.case_id,
                    "method": method,
                    "selected_place_ids": selected,
                    "selection_reasons_json": reasons,
                    "answer": answer,
                    "elapsed_seconds": perf_counter() - started,
                    "error": error,
                }
            )
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--methods", default="manual,dspy_baseline")
    parser.add_argument("--split", choices=("train", "dev", "test", "blind"), default="test")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).parent / "data",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    methods = tuple(item.strip() for item in args.methods.split(",") if item.strip())
    splits = load_dataset_splits(args.data_dir, allow_provisional=True)
    plan = build_evaluation_plan(splits, split=args.split, methods=methods)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0
    rows = run_evaluation(splits[args.split], methods=methods)
    output = args.output or Path(__file__).parent / "results" / f"{args.split}_results.jsonl"
    _write_jsonl(output, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
