"""실제 식당 DB + 임시 카페 후보의 Task별 10→3 종단 감사."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from routers.chat import _stream  # noqa: E402
from schemas.chat import ChatRequest  # noqa: E402
from schemas.structured_query import StructuredTravelQuery  # noqa: E402


async def main() -> None:
    parsed = StructuredTravelQuery.model_validate({
        "language": "ko",
        "intent": "single_place_recommendation",
        "source_mode": "rag_only",
        "original_question": "홍대에서 조용한 식당과 분위기 좋은 카페를 추천해줘",
        "normalized_question": "홍대 조용한 식당과 분위기 좋은 카페 추천",
        "tasks": [
            {
                "task_id": "restaurant_1",
                "domain": "restaurant",
                "search_query": "홍대 조용한 식당",
                "themes": ["조용한"],
            },
            {
                "task_id": "cafe_1",
                "domain": "cafe",
                "search_query": "홍대 분위기 좋은 카페",
                "themes": ["분위기 좋은"],
            },
        ],
        "filters": {"location": "홍대"},
    })
    body = ChatRequest(message=parsed.original_question, parsed_query=parsed)
    events = [event async for event in _stream(body)]
    decoded = [json.loads(event.removeprefix("data: ")) for event in events]
    error = next((event for event in decoded if event.get("type") == "error"), None)
    if error:
        raise RuntimeError(error["message"])
    meta = next(event for event in decoded if event.get("type") == "meta")
    answer = "".join(
        event.get("text", "") for event in decoded if event.get("type") == "token"
    )
    groups: dict[str, list[dict]] = {}
    for place in meta["places"]:
        groups.setdefault(place["task_id"], []).append({
            "domain": place["source_type"],
            "place_id": place["source_id"],
            "restaurant_id": place.get("restaurant_id"),
            "name": place["name"],
            "rank": place["rank"],
            "selection_reason": place["selection_reason"],
        })
    print(json.dumps({
        "intent": meta["intent"],
        "group_counts": {task_id: len(places) for task_id, places in groups.items()},
        "groups": groups,
        "answer": answer,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
