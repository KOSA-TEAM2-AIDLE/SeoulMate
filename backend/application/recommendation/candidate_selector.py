"""GPT가 반환한 ID가 전달 후보 안에 있는지 검증하는 공통 방어선."""

from domains.common.models import SearchCandidate


def validate_selected_ids(
    candidates: list[SearchCandidate],
    selected_ids: list[str],
    *,
    limit: int = 3,
) -> list[SearchCandidate]:
    allowed = {candidate.candidate_id: candidate for candidate in candidates}
    selected: list[SearchCandidate] = []
    seen: set[str] = set()
    for candidate_id in selected_ids:
        if candidate_id in allowed and candidate_id not in seen:
            selected.append(allowed[candidate_id])
            seen.add(candidate_id)
        if len(selected) >= limit:
            break
    # 잘못된 GPT ID나 부족한 선택은 기존 최종 순위로 복구한다.
    for candidate in candidates:
        if candidate.candidate_id not in seen and len(selected) < limit:
            selected.append(candidate)
            seen.add(candidate.candidate_id)
    return selected


__all__ = ["validate_selected_ids"]
