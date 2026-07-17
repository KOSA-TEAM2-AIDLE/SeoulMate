"""도메인 전용 선택 결과와 기존 공통 GPT 그룹 결과를 조정한다."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from application.recommendation.selection_models import (
    CandidateSelectionResult,
)
from application.recommendation.selection_registry import (
    DomainSelectionRegistry,
    build_default_selection_registry,
)
from domains.attraction.value_normalization import optional_text
from domains.common.models import DomainSearchRequest, SearchCandidate
from services.llm import (
    GROUP_SELECTION_COUNT,
    LLM_CANDIDATE_COUNT,
    generate_grouped_recommendation_result,
)


async def select_grouped_candidates(
    *,
    message: str,
    language: str,
    task_groups: list[dict],
    requests_by_task: dict[str, DomainSearchRequest],
    selection_registry: DomainSelectionRegistry | None = None,
    common_selector: Callable[..., dict] | None = None,
    weather: dict | None = None,
    source_mode: str = "rag_only",
) -> dict:
    """전용 Selector는 Task별 호출하고 나머지는 기존 GPT로 한 번 선택한다."""

    registry = selection_registry or build_default_selection_registry()
    common = common_selector or generate_grouped_recommendation_result
    common_groups: list[dict] = []
    custom_results: dict[str, dict] = {}
    custom_answers: dict[str, str] = {}
    fallback_used = False

    for group in task_groups:
        task_id = str(group["task_id"])
        domain = str(group["domain"])
        selector = registry.get_optional(domain)
        if selector is None:
            common_groups.append(group)
            continue
        request = requests_by_task.get(task_id)
        if request is None:
            raise ValueError(
                f"전용 선택기에 전달할 DomainSearchRequest가 없습니다: {task_id}"
            )
        candidates = _raw_candidates(group)
        selected = await selector.select(request, candidates)
        task_result, repaired = _custom_task_result(group, selected)
        custom_results[task_id] = task_result
        custom_answers[task_id] = selected.answer
        fallback_used = fallback_used or selected.used_fallback or repaired

    common_result: dict[str, Any] = {
        "answer": "",
        "task_results": [],
        "llm_fallback_used": False,
    }
    if common_groups:
        common_result = await asyncio.to_thread(
            common,
            message,
            language,
            common_groups,
            weather,
            source_mode,
        )
        fallback_used = fallback_used or bool(
            common_result.get("llm_fallback_used")
        )
    common_by_task = {
        str(result["task_id"]): result
        for result in common_result.get("task_results", [])
    }

    ordered_results: list[dict] = []
    answer_parts: list[str] = []
    common_answer_added = False
    for group in task_groups:
        task_id = str(group["task_id"])
        if task_id in custom_results:
            ordered_results.append(custom_results[task_id])
            answer = optional_text(custom_answers.get(task_id))
            if answer is not None:
                answer_parts.append(answer)
            continue
        result = common_by_task.get(task_id)
        if result is None:
            raise ValueError(f"공통 선택 결과에 Task가 없습니다: {task_id}")
        ordered_results.append(result)
        if not common_answer_added:
            answer = optional_text(common_result.get("answer"))
            if answer is not None:
                answer_parts.append(answer)
            common_answer_added = True

    if not answer_parts:
        answer_parts.append(
            "No verified recommendations are available."
            if language.casefold().startswith("en")
            else "검증된 추천 결과가 없습니다."
        )
        fallback_used = True
    return {
        "answer": "\n\n".join(answer_parts),
        "task_results": ordered_results,
        "llm_fallback_used": fallback_used,
    }


def _raw_candidates(group: dict) -> list[SearchCandidate]:
    candidates: list[SearchCandidate] = []
    for wrapped in group.get("candidates", [])[:LLM_CANDIDATE_COUNT]:
        raw = wrapped.get("raw_candidate")
        if not isinstance(raw, SearchCandidate):
            raise ValueError(
                f"{group['task_id']} 후보에 SearchCandidate가 없습니다."
            )
        candidates.append(raw)
    return candidates


def _custom_task_result(
    group: dict,
    result: CandidateSelectionResult,
) -> tuple[dict, bool]:
    pool = group.get("candidates", [])[:LLM_CANDIDATE_COUNT]
    wanted = min(GROUP_SELECTION_COUNT, len(pool))
    by_id = {str(candidate["place_id"]): candidate for candidate in pool}
    selections: list[dict] = []
    seen: set[str] = set()
    repaired = False

    for selection in result.selections:
        place_id = selection.place_id.strip()
        reason = optional_text(selection.selection_reason)
        if place_id not in by_id or place_id in seen or reason is None:
            repaired = True
            continue
        selections.append({
            "candidate": by_id[place_id],
            "selection_reason": reason,
        })
        seen.add(place_id)
        if len(selections) == wanted:
            break

    for candidate in pool:
        if len(selections) == wanted:
            break
        place_id = str(candidate["place_id"])
        if place_id in seen:
            continue
        repaired = True
        selections.append({
            "candidate": candidate,
            "selection_reason": (
                optional_text(candidate.get("fallback_reason"))
                or "요청 조건과 검색 순위를 종합해 선정했습니다."
            ),
        })
        seen.add(place_id)

    return ({
        "task_id": str(group["task_id"]),
        "domain": str(group["domain"]),
        "selections": selections,
    }, repaired)


__all__ = ["select_grouped_candidates"]
