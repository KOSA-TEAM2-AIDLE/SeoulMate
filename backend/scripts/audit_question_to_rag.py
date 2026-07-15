"""실제 GPT Structured Query → 검색 계획 → PostgreSQL RRF를 종단 검증한다."""

from __future__ import annotations

import asyncio
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from schemas.structured_query import StructuredTravelQuery  # noqa: E402
from services.query_policy import derive_source_mode  # noqa: E402
from services.rag import (  # noqa: E402
    build_restaurant_search_plan,
    search_restaurants_structured,
)


PARSER_SYSTEM_PROMPT = """
당신은 SeoulMate의 Structured Query Parser이자 데이터 소스 라우터입니다.
답변을 작성하지 말고 TravelQuery만 반환합니다.

[Intent]
- multi_day_route: 1박 이상 일정
- day_trip_route: 숙박 없는 하루 일정
- single_place_recommendation: 하나 또는 소수의 장소 추천
- weather_information: 장소 추천 없이 현재/미래 날씨만 질문
- general_response: 여행 처리와 날씨 조회가 모두 필요 없는 일반 질문

[SourceMode]
- rag_only: 장소·숙박·카페·식당·관광지 검색이 필요하지만 실제 현재/미래 날씨는 필요 없음
- rag_mcp: 도메인 검색과 실제 날씨 조회가 모두 필요함
- mcp_only: 장소 검색 없이 날씨 정보만 필요함
- general_response에서는 source_mode를 null로 반환

[판정 예시]
- "조용한 감성 카페 추천" → single_place_recommendation + rag_only
- "내일 저녁 조용한 감성 카페 추천" → single_place_recommendation + rag_mcp
- "내일 서울 날씨" → weather_information + mcp_only
- "비 오는 날 갈 문화시설 추천" → single_place_recommendation + rag_mcp
- "파이썬 리스트와 튜플 차이" → general_response + source_mode null

[Task]
- 하나의 Task는 하나의 domain만 가집니다.
- domain은 cafe, restaurant, accommodation, attraction, etc 중 하나입니다.
- Task는 최대 5개입니다.
- 복합 질문은 독립적으로 장소를 골라야 하는 요구 단위로 분리합니다. 같은 domain이어도 음식군·지역·목적이 다르면 별도 Task입니다.
- 여러 장소를 나열해 추천해 달라는 말만으로 day_trip_route로 분류하지 않습니다. 일정·동선·코스·방문 순서를 요청할 때만 route intent를 사용합니다.
- 질문에 없는 조건을 추가하지 않습니다.
- mcp_only와 general_response에서는 tasks를 빈 리스트로 반환합니다.

[WeatherRequest]
- rag_mcp 또는 mcp_only일 때만 생성합니다.
- query에는 날짜·시간 표현이 보존되도록 사용자 원문 전체를 넣습니다.
- target_date와 target_time은 현재 날짜를 기준으로 해석할 수 있을 때만 채웁니다.
- location_name은 사용자가 명시한 경우에만 채웁니다.
- 위도·경도는 만들지 않습니다. 좌표는 UserContext에서 결합합니다.
- language는 사용자 질문 언어와 동일하게 설정합니다.

[Filter]
- 명시되거나 UserContext에 제공된 정보만 사용합니다.
- 현재 좌표는 filters에 복사하지 않습니다.
- 날짜는 가능한 경우 YYYY-MM-DD로 해석합니다.
- 모든 Task에 공통인 조건은 TravelQuery.filters에 넣습니다.
- 지역·날짜·시간·예산 등이 Task마다 다르면 해당 QueryTask.filters에 넣고, 전역 filters에는 억지로 하나를 고르지 않습니다.

[검증]
- rag_only: Task 있음, WeatherRequest 없음
- rag_mcp: Task 있음, WeatherRequest 있음
- mcp_only: Task 없음, WeatherRequest 있음, intent=weather_information
- general_response: Task/WeatherRequest/source_mode 없음, general_response_instruction 있음
"""

PARSER_HUMAN_PROMPT = """
[현재 날짜]
{today}

[사용자 컨텍스트]
{user_context}

[사용자 질문]
{question}

TravelQuery 스키마로 구조화하세요.
"""


QUESTIONS = [
    "홍대에서 중식당을 찾고 있어. 평점 4.5 이상이고 1인 메뉴 가격은 3만원 이하였으면 좋겠어.",
    "지금 강남역 반경 2km 안에서 영업 중이고 주차 가능한 한식당 추천해줘.",
    "내일 저녁 성수에서 반려동물과 함께 갈 수 있는 조용한 이탈리안 식당을 찾고 있어.",
    "이번 토요일 오후 3시에 종로에서 휠체어 접근이 가능한 식당을 추천해줘. 일식이면 좋아.",
    "을지로에서 모임할 거야. 단체석과 룸이 모두 있는 식당으로 부탁하고 예산은 2만원에서 5만원 사이야.",
    "Find a quiet Chinese restaurant within 3 km of Hongdae, rated 4.3 or higher, with parking.",
    "홍대에서 마라탕 먹고 싶어. 시끄러운 술집 말고 대화하기 편한 식당이면 좋겠어.",
    "주차는 없어도 괜찮아. 서울에서 평점 좋은 태국 음식점 추천해줘.",
]


def _candidate_violations(candidate: dict, plan) -> list[str]:
    violations: list[str] = []
    if plan.min_rating is not None:
        if candidate.get("rating") is None or candidate["rating"] < plan.min_rating:
            violations.append("rating")
    if plan.origin_lat is not None and candidate.get("distance_km") is not None:
        if candidate["distance_km"] > plan.radius_km + 1e-6:
            violations.append("distance")
    if plan.target_visit_at and candidate.get("open_status") is False:
        violations.append("opening_hours")
    if plan.open_now and candidate.get("open_status") is not True:
        violations.append("open_now")
    if plan.budget_min_krw is not None:
        price = candidate.get("menu_price_median")
        if price is None or price < plan.budget_min_krw:
            violations.append("budget_min")
    if plan.budget_max_krw is not None:
        price = candidate.get("menu_price_median")
        if price is None or price > plan.budget_max_krw:
            violations.append("budget_max")
    for field in plan.required_feature_fields:
        if candidate.get(field) is not True:
            violations.append(field)
    for field in plan.excluded_feature_fields:
        if candidate.get(field) is True:
            violations.append(f"excluded:{field}")
    if plan.requested_category:
        status = candidate.get("breakdown", {}).get("category_status")
        if status not in {"match", "no_data"}:
            violations.append("category")
    return violations


async def main(summary_only: bool = False) -> None:
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = ChatPromptTemplate.from_messages(
        [("system", PARSER_SYSTEM_PROMPT), ("human", PARSER_HUMAN_PROMPT)]
    )
    parser = prompt | ChatOpenAI(model=model_name, temperature=0).with_structured_output(
        StructuredTravelQuery,
        method="function_calling",
    )
    user_context = {
        "current_location": {"latitude": 37.5665, "longitude": 126.9780},
        "location_name": None,
        "timezone": "Asia/Seoul",
    }
    parsed_items = await asyncio.gather(*[
        parser.ainvoke({
            "today": date.today().isoformat(),
            "user_context": json.dumps(user_context, ensure_ascii=False),
            "question": question,
        })
        for question in QUESTIONS
    ])

    summaries = []
    total_violations = 0
    for question, parsed in zip(QUESTIONS, parsed_items):
        restaurant_tasks = [task for task in parsed.tasks if task.domain == "restaurant"]
        if not restaurant_tasks:
            summaries.append({
                "question": question,
                "parser": parsed.model_dump(mode="json"),
                "error": "restaurant task missing",
            })
            total_violations += 1
            continue
        task = restaurant_tasks[0]
        location = parsed.filters.location
        # 실제 검색에서는 타깃 위치를 Kakao로 지오코딩한다. 파서/검색어 감사 중
        # 외부 지오코딩 실패가 결과를 흔들지 않도록 위치 필터만 없는 경우에 현재 좌표를 쓴다.
        plan = build_restaurant_search_plan(
            parsed,
            task,
            current_lat=37.5665,
            current_lng=126.9780,
            current_location_name=None,
            top_n=30,
        )
        result = search_restaurants_structured(
            parsed,
            task,
            current_lat=plan.origin_lat,
            current_lng=plan.origin_lng,
            current_location_name=plan.location_name,
            top_n=30,
        )
        violations = [
            {
                "restaurant_id": candidate["restaurant_id"],
                "violations": _candidate_violations(candidate, plan),
            }
            for candidate in result["candidates"]
            if _candidate_violations(candidate, plan)
        ]
        total_violations += len(violations)
        summaries.append({
            "question": question,
            "parser": parsed.model_dump(mode="json"),
            "derived_source_mode": derive_source_mode(parsed),
            "rag_plan": {
                "restaurant_query": plan.retrieval_query,
                "review_query": plan.review_query,
                "menu_query": plan.menu_query,
                "requested_category": plan.requested_category,
                "radius_km": plan.radius_km,
                "min_rating": plan.min_rating,
                "target_visit_at": plan.target_visit_at.isoformat() if plan.target_visit_at else None,
                "budget_min_krw": plan.budget_min_krw,
                "budget_max_krw": plan.budget_max_krw,
                "required_features": list(plan.required_feature_fields),
                "excluded_features": list(plan.excluded_feature_fields),
            },
            "candidate_count": len(result["candidates"]),
            "top_candidates": [
                {
                    "restaurant_id": candidate["restaurant_id"],
                    "name": candidate["name"],
                    "rating": candidate["rating"],
                    "distance_km": candidate["distance_km"],
                    "open_status": candidate["open_status"],
                    "menu_price_median": candidate["menu_price_median"],
                    "rrf": candidate["breakdown"],
                }
                for candidate in result["candidates"][:3]
            ],
            "filter_violations": violations,
        })

    report = {
        "model": model_name,
        "case_count": len(QUESTIONS),
        "filter_violation_count": total_violations,
        "cases": summaries,
    }
    if summary_only:
        compact = {
            "model": model_name,
            "case_count": len(QUESTIONS),
            "filter_violation_count": total_violations,
            "cases": [
                {
                    "question": item["question"],
                    "mode": item.get("derived_source_mode"),
                    "rag_plan": item.get("rag_plan"),
                    "candidate_count": item.get("candidate_count", 0),
                    "top_candidates": item.get("top_candidates", []),
                    "filter_violations": item.get("filter_violations", []),
                }
                for item in summaries
            ],
        }
        print(json.dumps(compact, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--summary", action="store_true")
    arguments = argument_parser.parse_args()
    asyncio.run(main(summary_only=arguments.summary))
