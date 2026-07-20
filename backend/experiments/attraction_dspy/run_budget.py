"""DSPy candidate run 비용 상한을 유료 호출 전에 계산한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import tiktoken

from experiments.attraction_dspy.production_dataset import (
    load_production_splits,
    to_answer_example,
    to_selection_example,
)


INPUT_USD_PER_MILLION = 0.15
OUTPUT_USD_PER_MILLION = 0.60
SELECTION_MAX_OUTPUT_TOKENS = 900
ANSWER_MAX_OUTPUT_TOKENS = 1500
_PROPOSER_CALLS_PER_PROGRAM = 16


def estimate_run_budget(
    data_dir: Path,
    *,
    num_trials: int,
    include_full_evaluation: bool,
) -> dict[str, Any]:
    """Return a conservative upper estimate for a two-program candidate run."""
    if num_trials < 1:
        raise ValueError("num_trials는 1 이상이어야 합니다.")

    selection = load_production_splits(data_dir, "selection")
    answer = load_production_splits(data_dir, "answer")
    optimization_calls = sum(
        _PROPOSER_CALLS_PER_PROGRAM + len(splits["dev"]) * num_trials
        for splits in (selection, answer)
    )
    evaluation_calls = 0
    if include_full_evaluation:
        gold = load_production_splits(data_dir, "gold_test")["test"]
        evaluation_calls = (len(selection["test"]) + len(gold)) * 3

    input_tokens = _estimated_input_tokens(
        selection,
        answer,
        num_trials=num_trials,
        include_full_evaluation=include_full_evaluation,
        data_dir=data_dir,
    )
    total_calls = optimization_calls + evaluation_calls
    output_token_cap = _output_token_cap(
        selection=selection,
        answer=answer,
        num_trials=num_trials,
        include_full_evaluation=include_full_evaluation,
        data_dir=data_dir,
    )
    estimated_cost = (
        input_tokens / 1_000_000 * INPUT_USD_PER_MILLION
        + output_token_cap / 1_000_000 * OUTPUT_USD_PER_MILLION
    )
    return {
        "optimization_calls": optimization_calls,
        "evaluation_calls": evaluation_calls,
        "total_calls": total_calls,
        "estimated_input_tokens": input_tokens,
        "output_token_cap": output_token_cap,
        "estimated_cost_usd": round(estimated_cost, 4),
    }


def require_within_budget(estimate: dict[str, Any], max_usd: float) -> None:
    if max_usd <= 0:
        raise ValueError("비용 상한은 0보다 커야 합니다.")
    cost = float(estimate["estimated_cost_usd"])
    if cost > max_usd:
        raise ValueError(
            f"예상 비용이 비용 상한을 초과합니다: ${cost:.4f} > ${max_usd:.4f}"
        )


def _estimated_input_tokens(
    selection: dict[str, list],
    answer: dict[str, list],
    *,
    num_trials: int,
    include_full_evaluation: bool,
    data_dir: Path,
) -> int:
    encoder = tiktoken.encoding_for_model("gpt-4o-mini")
    selection_dev = _tokens(selection["dev"], to_selection_example, encoder)
    answer_dev = _tokens(answer["dev"], to_answer_example, encoder)
    selection_average = _average_tokens(selection_dev)
    answer_average = _average_tokens(answer_dev)

    total = (
        sum(selection_dev) * num_trials
        + sum(answer_dev) * num_trials
        + selection_average * _PROPOSER_CALLS_PER_PROGRAM
        + answer_average * _PROPOSER_CALLS_PER_PROGRAM
    )
    if not include_full_evaluation:
        return total

    selection_test = _tokens(selection["test"], to_selection_example, encoder)
    answer_test = _tokens(answer["test"], to_answer_example, encoder)
    gold = load_production_splits(data_dir, "gold_test")["test"]
    gold_selection = _tokens(gold, to_selection_example, encoder)
    gold_answer = _tokens(gold, to_answer_example, encoder)
    # Legacy uses a selection-shaped input once; split uses selection and answer once.
    return total + 2 * (sum(selection_test) + sum(gold_selection)) + sum(answer_test) + sum(gold_answer)


def _output_token_cap(
    *,
    selection: dict[str, list],
    answer: dict[str, list],
    num_trials: int,
    include_full_evaluation: bool,
    data_dir: Path,
) -> int:
    selection_optimization = _PROPOSER_CALLS_PER_PROGRAM + len(selection["dev"]) * num_trials
    answer_optimization = _PROPOSER_CALLS_PER_PROGRAM + len(answer["dev"]) * num_trials
    cap = (
        selection_optimization * SELECTION_MAX_OUTPUT_TOKENS
        + answer_optimization * ANSWER_MAX_OUTPUT_TOKENS
    )
    if not include_full_evaluation:
        return cap
    evaluated = len(selection["test"]) + len(load_production_splits(data_dir, "gold_test")["test"])
    # Legacy single program + split selection + split answer per case.
    return cap + evaluated * (
        2 * SELECTION_MAX_OUTPUT_TOKENS + ANSWER_MAX_OUTPUT_TOKENS
    )


def _tokens(cases: list, factory, encoder) -> list[int]:
    return [_example_tokens(factory(case), encoder) for case in cases]


def _example_tokens(example, encoder) -> int:
    payload = {name: getattr(example, name) for name in example.inputs()}
    return len(encoder.encode(json.dumps(payload, ensure_ascii=False, sort_keys=True)))


def _average_tokens(tokens: list[int]) -> int:
    return max(1, round(sum(tokens) / len(tokens)))
