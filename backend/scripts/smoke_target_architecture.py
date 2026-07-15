"""새 목표 구조에서 실제 식당 DB/RAG가 연결됐는지 확인하는 작은 smoke test."""

from __future__ import annotations

import asyncio
import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

from application.recommendation.orchestrator import RecommendationOrchestrator
from schemas.structured_query import StructuredTravelQuery


async def main(with_weather: bool = False) -> None:
    source_mode = "rag_mcp" if with_weather else "rag_only"
    question = (
        "내일 저녁 홍대에서 조용한 식당 추천해줘"
        if with_weather else "홍대에서 조용한 식당 추천해줘"
    )
    parsed = StructuredTravelQuery.model_validate({
        "language": "ko",
        "intent": "single_place_recommendation",
        "original_question": question,
        "normalized_question": question,
        "source_mode": source_mode,
        "filters": {
            "location": "홍대",
            **({"start_date": "2026-07-16", "time_window": "evening"} if with_weather else {}),
        },
        "tasks": [{
            "task_id": "task_1",
            "domain": "restaurant",
            "search_query": "홍대 조용한 식당",
            "themes": ["조용한"],
            "desired_count": 1,
        }],
    })
    results = await RecommendationOrchestrator().execute(parsed, candidate_count=3)
    output = {
        "source_mode": results[0].source_mode,
        "weather_available": (
            results[0].contexts.get("weather", {}).get("available")
            if with_weather else None
        ),
        "warnings": results[0].warnings,
        "candidate_count": len(results[0].candidates),
        "candidates": [
            {
                "candidate_id": item.candidate_id,
                "name": item.name,
                "base_score": item.base_score,
                "final_score": item.final_score,
                "weather_reasons": item.signals.get("weather_reasons", []),
            }
            for item in results[0].candidates
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if not results[0].candidates:
        raise RuntimeError("실제 식당 RAG 후보가 없습니다.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-weather", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(with_weather=args.with_weather))
