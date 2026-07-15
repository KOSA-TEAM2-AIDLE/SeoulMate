"""사용자 원문부터 GPT 파서·RAG/MCP·최종 GPT까지 반복 종단 감사."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from routers.chat import _stream  # noqa: E402
from schemas.chat import ChatRequest  # noqa: E402
from schemas.structured_query import StructuredTravelQuery  # noqa: E402
from scripts.audit_question_to_rag import (  # noqa: E402
    PARSER_HUMAN_PROMPT,
    PARSER_SYSTEM_PROMPT,
)
from services.query_policy import derive_source_mode, effective_task_filters  # noqa: E402
from services.query_policy import deduplicate_recommendation_tasks  # noqa: E402


CASES = [
    {
        "id": "simple_restaurant",
        "question": "홍대에서 조용하게 대화하기 좋은 중식당 추천해줘.",
        "expected_domains": ["restaurant"],
    },
    {
        "id": "future_restaurant",
        "question": "내일 저녁 성수에서 반려동물과 갈 수 있는 이탈리안 식당 추천해줘.",
        "expected_domains": ["restaurant"],
    },
    {
        "id": "restaurant_cafe",
        "question": "홍대에서 저녁 먹을 식당과 분위기 좋은 카페를 추천해줘.",
        "expected_domains": ["restaurant", "cafe"],
    },
    {
        "id": "future_restaurant_cafe",
        "question": "내일 홍대에서 조용한 저녁 식당과 비가 와도 가기 편한 카페를 추천해줘.",
        "expected_domains": ["restaurant", "cafe"],
    },
    {
        "id": "hard_filters",
        "question": "강남역 2km 안에서 평점 4.5 이상이고 주차 가능하며 5만원 이하인 한식당 추천해줘.",
        "expected_domains": ["restaurant"],
    },
    {
        "id": "optional_negation",
        "question": "주차는 없어도 괜찮아. 서울에서 평점 좋은 태국 음식점 추천해줘.",
        "expected_domains": ["restaurant"],
    },
    {
        "id": "specific_menu",
        "question": "홍대에서 마라탕 먹고 싶어. 시끄러운 술집 말고 대화하기 편한 곳으로 추천해줘.",
        "expected_domains": ["restaurant"],
        # 현재 DB에는 홍대 기본 반경 안에서 마라탕 메뉴가 확인된 식당이 없다.
        # 비슷한 중식당을 거짓 대체하지 않고 명시적 빈 결과를 내는 것이 정상이다.
        "allow_empty": True,
    },
    {
        "id": "english_restaurant",
        "question": "Find a quiet Chinese restaurant within 3 km of Hongdae, rated 4.3 or higher, with parking.",
        "expected_domains": ["restaurant"],
    },
    {
        "id": "three_domains",
        "question": "종로에서 한식당, 조용한 카페, 실내 문화시설을 각각 추천해줘.",
        "expected_domains": ["restaurant", "cafe", "attraction"],
    },
    {
        "id": "two_restaurant_needs",
        "question": "홍대에서 한식당과 중식당을 각각 추천해줘.",
        "expected_domains": ["restaurant", "restaurant"],
    },
    {
        "id": "different_locations",
        "question": "홍대에서는 식당을 추천하고 강남에서는 분위기 좋은 카페를 추천해줘.",
        "expected_domains": ["restaurant", "cafe"],
    },
    {
        "id": "day_route_two_slots",
        "question": "내일 홍대에서 저녁을 먹고 분위기 좋은 카페 한 곳도 가고 싶어.",
        "expected_domains": ["restaurant", "cafe"],
        "route": True,
        "expected_intent": "day_trip_route",
        "expected_days": 1,
    },
    {
        "id": "day_route_five_slots",
        "question": "내일 서울에서 명소, 점심 한식당, 카페, 실내 문화시설, 저녁 식당 순서로 총 5곳 하루 코스를 짜줘.",
        "expected_domains": ["attraction", "restaurant", "cafe", "attraction", "restaurant"],
        "route": True,
        "expected_intent": "day_trip_route",
        "expected_days": 1,
    },
    {
        "id": "multi_route_one_night",
        "question": "이번 토요일부터 서울 1박 2일 여행이야. 1일차는 관광지, 점심 식당, 카페, 숙소 순서로 가고 2일차는 관광지, 점심 식당, 카페, 저녁 식당 순서로 짜줘.",
        "expected_domains": ["attraction", "restaurant", "cafe", "accommodation", "attraction", "restaurant", "cafe", "restaurant"],
        "route": True,
        "expected_intent": "multi_day_route",
        "expected_days": 2,
    },
    {
        "id": "english_day_route",
        "question": "Plan a one-day Seoul route for tomorrow with one attraction, lunch, a cafe, and dinner.",
        "expected_domains": ["attraction", "restaurant", "cafe", "restaurant"],
        "route": True,
        "expected_intent": "day_trip_route",
        "expected_days": 1,
    },
    {
        "id": "weather_only",
        "question": "내일 저녁 서울 날씨 알려줘.",
        "expected_domains": [],
    },
    {
        "id": "general",
        "question": "서울의 행정구역은 몇 개야?",
        "expected_domains": [],
    },
]


def _decode_sse(events: list[str]) -> list[dict]:
    decoded = []
    for event in events:
        try:
            decoded.append(json.loads(event.removeprefix("data: ")))
        except json.JSONDecodeError:
            decoded.append({"type": "decode_error", "raw": event[:200]})
    return decoded


async def _run_once(chain, case: dict, run: int, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        started = time.perf_counter()
        errors: list[str] = []
        warnings: list[str] = []
        try:
            parsed = await chain.ainvoke({
                "today": date.today().isoformat(),
                "user_context": json.dumps({
                    "current_location": {"latitude": 37.5665, "longitude": 126.9780},
                    "location_name": None,
                    "timezone": "Asia/Seoul",
                }, ensure_ascii=False),
                "question": case["question"],
            })
        except Exception as exc:
            return {
                "case_id": case["id"], "run": run, "ok": False,
                "errors": [f"parser:{type(exc).__name__}:{exc}"],
                "elapsed_sec": round(time.perf_counter() - started, 3),
            }

        raw_task_domains = [task.domain for task in parsed.tasks]
        expected = case["expected_domains"]
        normalized_parsed = deduplicate_recommendation_tasks(parsed)
        normalized_domains = [task.domain for task in normalized_parsed.tasks]
        if expected is not None and Counter(raw_task_domains) != Counter(expected):
            warnings.append(
                f"parser_domains expected={expected} actual={raw_task_domains}"
            )
        if expected is not None and Counter(normalized_domains) != Counter(expected):
            errors.append(
                f"normalized_domains expected={expected} actual={normalized_domains}"
            )
        if not case.get("route") and len(parsed.tasks) > 5:
            errors.append(f"too_many_tasks={len(parsed.tasks)}")
        if case.get("route") and parsed.intent != case["expected_intent"]:
            errors.append(f"route_intent expected={case['expected_intent']} actual={parsed.intent}")
        task_ids = [task.task_id for task in parsed.tasks]
        if len(task_ids) != len(set(task_ids)):
            errors.append("duplicate_task_ids")

        body = ChatRequest(
            message=case["question"],
            parsed_query=normalized_parsed,
            lat=37.5665,
            lng=126.9780,
            location_name=None,
        )
        events = _decode_sse([event async for event in _stream(body)])
        backend_errors = [event.get("message") for event in events if event.get("type") == "error"]
        errors.extend(f"backend:{message}" for message in backend_errors)
        meta = next((event for event in events if event.get("type") == "meta"), {})
        places = meta.get("places", [])
        counts = Counter(place.get("task_id") for place in places if place.get("task_id"))
        if case.get("route"):
            days = meta.get("days") or []
            result = meta.get("result") or {}
            expected_api_intent = (
                "route_multi" if case["expected_intent"] == "multi_day_route" else "route_day"
            )
            if meta.get("intent") != expected_api_intent:
                errors.append(f"meta_intent expected={expected_api_intent} actual={meta.get('intent')}")
            if len(days) != case["expected_days"]:
                errors.append(f"day_count expected={case['expected_days']} actual={len(days)}")
            empty_days = [day.get("day") for day in days if not (day.get("slots") or [])]
            if empty_days:
                errors.append(f"empty_route_days={empty_days}")
            if result.get("responseType") != "route":
                errors.append("missing_route_frontend_result")
            if result.get("allDay") != case["expected_days"]:
                errors.append(f"allDay={result.get('allDay')}")
            travel_path = result.get("travelPath") or {}
            expected_keys = {str(day) for day in range(1, case["expected_days"] + 1)}
            if set(travel_path) != expected_keys:
                errors.append(f"travelPath_keys={sorted(travel_path)}")
            places = [
                slot.get("place", {})
                for day in days
                for slot in (day.get("slots") or [])
            ]
            if len(places) != len(normalized_parsed.tasks):
                errors.append(
                    f"route_place_count tasks={len(normalized_parsed.tasks)} places={len(places)}"
                )
            slot_ids = [
                slot.get("slot_id")
                for day in days
                for slot in (day.get("slots") or [])
            ]
            if len(slot_ids) != len(set(slot_ids)):
                errors.append("duplicate_output_slot_ids")
            place_keys = [
                (place.get("source_type"), str(place.get("source_id")))
                for place in places
            ]
            if len(place_keys) != len(set(place_keys)):
                errors.append("duplicate_output_places")
        elif normalized_parsed.tasks and not places and not backend_errors and not case.get("allow_empty"):
            errors.append("empty_recommendations")
        if case.get("allow_empty") and places:
            errors.append("expected_verified_empty_result")
        if not case.get("route") and len(normalized_parsed.tasks) > 1:
            for task in normalized_parsed.tasks:
                if counts.get(task.task_id, 0) == 0:
                    errors.append(f"task_not_selected:{task.task_id}")
                if counts.get(task.task_id, 0) > 3:
                    errors.append(f"task_over_selected:{task.task_id}={counts[task.task_id]}")
                if counts.get(task.task_id, 0) and any(
                    place.get("source_type") != task.domain
                    for place in places if place.get("task_id") == task.task_id
                ):
                    errors.append(f"domain_mix:{task.task_id}")
        if any(not place.get("selection_reason") for place in places):
            errors.append("missing_selection_reason")
        answer = "".join(event.get("text", "") for event in events if event.get("type") == "token")
        internal_terms = (
            "RAG 점수", "weather_reasons", "후보 데이터", "confirmed_features",
            "private_room", "group_seating", "baby_chair", "has_parking",
            "has_disabled_access", "allows_pets", "has_kids_menu",
        )
        if any(term in answer for term in internal_terms):
            errors.append("internal_term_exposed")
        if any(
            term in (place.get("selection_reason") or "")
            for place in places
            for term in (*internal_terms, "rag_score")
        ):
            errors.append("internal_term_in_selection_reason")
        if not answer.strip():
            errors.append("empty_answer")
        if case["id"] == "different_locations" and parsed.tasks:
            locations = {
                task.domain: effective_task_filters(parsed, task).location
                for task in parsed.tasks
            }
            if locations.get("restaurant") != "홍대" or locations.get("cafe") != "강남":
                errors.append(f"task_locations={locations}")

        return {
            "case_id": case["id"],
            "run": run,
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "elapsed_sec": round(time.perf_counter() - started, 3),
            "parsed": parsed.model_dump(mode="json"),
            "derived_source_mode": derive_source_mode(parsed),
            "meta_intent": meta.get("intent"),
            "place_counts": dict(counts),
            "places": [
                {
                    "task_id": place.get("task_id"),
                    "domain": place.get("source_type"),
                    "id": place.get("source_id"),
                    "name": place.get("name"),
                    "rank": place.get("rank"),
                    "reason": place.get("selection_reason"),
                }
                for place in places
            ],
            "answer": answer,
        }


async def main(repeat: int, full: bool, case_ids: set[str] | None = None) -> None:
    chain = ChatPromptTemplate.from_messages([
        ("system", PARSER_SYSTEM_PROMPT),
        ("human", PARSER_HUMAN_PROMPT),
    ]) | ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0).with_structured_output(
        StructuredTravelQuery,
        method="function_calling",
    )
    semaphore = asyncio.Semaphore(3)
    selected_cases = [case for case in CASES if not case_ids or case["id"] in case_ids]
    results = await asyncio.gather(*[
        _run_once(chain, case, run, semaphore)
        for run in range(1, repeat + 1)
        for case in selected_cases
    ])
    by_case: dict[str, list[dict]] = {}
    for result in results:
        by_case.setdefault(result["case_id"], []).append(result)
    exact_consistency = {}
    structural_consistency = {}
    for case_id, items in by_case.items():
        signatures = [
            [
                (task["domain"], task["search_query"], tuple(task.get("themes", [])))
                for task in item.get("parsed", {}).get("tasks", [])
            ]
            for item in items
        ]
        exact_consistency[case_id] = len({json.dumps(value, ensure_ascii=False) for value in signatures}) == 1
        domain_signatures = [
            [(task["domain"], (task.get("filters") or {}).get("location"))
             for task in item.get("parsed", {}).get("tasks", [])]
            for item in items
        ]
        structural_consistency[case_id] = len({
            json.dumps(value, ensure_ascii=False) for value in domain_signatures
        }) == 1
    summary = {
        "case_count": len(selected_cases),
        "repeat": repeat,
        "run_count": len(results),
        "passed": sum(item["ok"] for item in results),
        "failed": sum(not item["ok"] for item in results),
        "parser_structural_consistency": structural_consistency,
        "parser_exact_wording_consistency": exact_consistency,
        "failures": [
            {"case_id": item["case_id"], "run": item["run"], "errors": item["errors"]}
            for item in results if not item["ok"]
        ],
        "warnings": [
            {"case_id": item["case_id"], "run": item["run"], "warnings": item.get("warnings", [])}
            for item in results if item.get("warnings")
        ],
        "average_elapsed_sec": round(
            sum(item["elapsed_sec"] for item in results) / len(results), 3
        ),
        "results": results if full else [
            {
                "case_id": item["case_id"], "run": item["run"], "ok": item["ok"],
                "errors": item["errors"], "warnings": item.get("warnings", []),
                "elapsed_sec": item["elapsed_sec"],
                "domains": [task["domain"] for task in item.get("parsed", {}).get("tasks", [])],
                "task_queries": [
                    task.get("search_query")
                    for task in item.get("parsed", {}).get("tasks", [])
                ],
                "source_mode": item.get("derived_source_mode"),
                "place_counts": item.get("place_counts"),
                "place_names": [place["name"] for place in item.get("places", [])],
            }
            for item in results
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--case", action="append", dest="case_ids")
    args = parser.parse_args()
    asyncio.run(main(max(1, args.repeat), args.full, set(args.case_ids or [])))
