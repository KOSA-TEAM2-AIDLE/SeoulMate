"""아직 검색기가 없는 도메인의 교체 가능한 임시 Agent 구현."""

from __future__ import annotations

from schemas.common import Place
from schemas.structured_query import StructuredQueryTask


MOCK_DOMAIN_LABELS = {
    "restaurant": ("임시 식당 후보", "식당"),
    "cafe": ("임시 카페 후보", "카페"),
    "attraction": ("임시 문화시설 후보", "문화시설"),
    "accommodation": ("임시 숙소 후보", "숙박시설"),
    "etc": ("임시 기타 장소 후보", "기타"),
    "accommodation" : ("임시 숙소 장소 후보","숙소")
}


def mock_places_for_task(
    task: StructuredQueryTask,
    *,
    lat: float | None = None,
    lng: float | None = None,
    candidate_count: int | None = None,
) -> list[Place]:
    """Domain Agent가 연결될 때까지 요청 수만큼 명시적 임시 후보를 반환한다."""
    if task.domain == "restaurant":
        raise ValueError("restaurant Task는 실제 RestaurantAgent를 사용해야 합니다.")

    base_name, category = MOCK_DOMAIN_LABELS[task.domain]
    count = (
        min(max(candidate_count, 1), 100)
        if candidate_count is not None
        else min(max(task.desired_count, 1), 3)
    )
    return [
        Place(
            source_type=task.domain,
            # 같은 임시 장소는 Task가 달라도 같은 ID를 가져야 Route Planner가
            # 한 루트 안의 중복 방문으로 인식할 수 있다.
            source_id=f"mock-{task.domain}-{index}",
            task_id=task.task_id,
            name=f"{base_name} {index}",
            category=category,
            score=max(0.1, 1.0 - (index - 1) * 0.1),
            reason=(
                f"{task.domain} 검색 알고리즘 연결 전 사용하는 고정 응답입니다. "
                f"검색 조건: {task.search_query}"
            ),
            lat=lat,
            lng=lng,
            rag_score=None,
            weather_score=None,
            weather_reasons=[],
        )
        for index in range(1, count + 1)
    ]


def is_mock_domain(domain: str) -> bool:
    return domain in MOCK_DOMAIN_LABELS


__all__ = ["is_mock_domain", "mock_places_for_task"]
