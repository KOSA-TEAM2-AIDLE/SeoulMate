from __future__ import annotations

import json
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

from core.config import DB_CONFIG
from schemas.structured_query import StructuredTravelQuery
from services.rag import build_restaurant_search_plan, search_restaurants_structured


CASES = [
    {
        "label": "홍대 조용한 중식당",
        "question": "홍대에서 조용한 중식당 추천해줘",
        "search_query": "홍대 조용한 중식당",
        "themes": ["조용한"],
        "location": "홍대",
        "language": "ko",
        "expected_category": True,
    },
    {
        "label": "강남 분위기 좋은 이탈리안",
        "question": "강남에서 분위기 좋은 이탈리안 식당 추천해줘",
        "search_query": "강남 분위기 좋은 이탈리안 식당",
        "themes": ["분위기 좋은"],
        "location": "강남",
        "language": "ko",
        "expected_category": True,
    },
    {
        "label": "현재 영업 중 일식",
        "question": "홍대에서 지금 영업 중인 일식당 추천해줘",
        "search_query": "홍대 영업 중인 일식당",
        "themes": [],
        "location": "홍대",
        "language": "ko",
        "is_active": True,
        "expected_category": True,
        "require_open": True,
    },
    {
        "label": "반려동물+주차+평점",
        "question": "홍대에서 평점 4.0 이상이고 반려동물 동반과 주차 가능한 식당 추천해줘",
        "search_query": "홍대 평점 4.0 이상 반려동물 동반 주차 가능한 식당",
        "themes": [],
        "location": "홍대",
        "language": "ko",
        "required_features": ["반려동물 동반", "주차"],
        "min_rating": 4.0,
    },
    {
        "label": "English Chinese",
        "question": "Find a quiet Chinese restaurant in Hongdae tomorrow evening",
        "search_query": "Hongdae quiet Chinese restaurant",
        "themes": ["quiet"],
        "location": "Hongdae",
        "language": "en",
        "start_date": "2026-07-15",
        "time_window": "evening",
        "expected_category": True,
        "require_visit_open": True,
    },
    {
        "label": "내일 저녁 홍대 한식",
        "question": "내일 저녁 홍대에서 한식당 추천해줘",
        "search_query": "홍대 한식당",
        "themes": ["저녁"],
        "location": "홍대",
        "language": "ko",
        "start_date": "2026-07-15",
        "time_window": "evening",
        "expected_category": True,
        "require_visit_open": True,
    },
    {
        "label": "3만원 이하 단체석",
        "question": "홍대에서 3만원 이하이고 단체석 있는 식당 추천해줘",
        "search_query": "홍대 단체석 있는 식당",
        "themes": [],
        "location": "홍대",
        "language": "ko",
        "budget_max_krw": 30000,
        "required_features": ["단체석"],
    },
]


def make_query(case: dict) -> StructuredTravelQuery:
    return StructuredTravelQuery.model_validate({
        "language": case["language"],
        "intent": "single_place_recommendation",
        "original_question": case["question"],
        "normalized_question": case["question"],
        "tasks": [{
            "task_id": "task_1",
            "domain": "restaurant",
            "search_query": case["search_query"],
            "themes": case.get("themes", []),
            "desired_count": 3,
        }],
        "filters": {
            "location": case["location"],
            "is_active": case.get("is_active"),
            "start_date": case.get("start_date"),
            "time_window": case.get("time_window"),
            "required_features": case.get("required_features", []),
            "budget_min_krw": case.get("budget_min_krw"),
            "budget_max_krw": case.get("budget_max_krw"),
        },
    })


def coverage() -> None:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for suffix in ("ko", "en"):
                cur.execute(f"""
                    SELECT COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE lat IS NOT NULL AND lng IS NOT NULL) AS coordinates,
                           COUNT(*) FILTER (WHERE rating IS NOT NULL) AS ratings,
                           COUNT(*) FILTER (WHERE hours IS NOT NULL AND hours <> '') AS hours,
                           COUNT(*) FILTER (WHERE has_parking IS NOT NULL) AS parking_known,
                           COUNT(*) FILTER (WHERE allows_pets IS NOT NULL) AS pets_known,
                           COUNT(*) FILTER (WHERE has_kids_menu IS NOT NULL) AS kids_known,
                           COUNT(*) FILTER (WHERE description IS NOT NULL AND description <> '') AS descriptions,
                           COUNT(*) FILTER (WHERE description_kakao IS NOT NULL AND description_kakao <> '') AS kakao_descriptions
                    FROM restaurant_{suffix}
                """)
                print("COVERAGE", suffix, json.dumps(dict(cur.fetchone()), ensure_ascii=False, default=str))
            cur.execute("""
                SELECT category_kakao, COUNT(*) AS count
                FROM restaurant_ko
                GROUP BY category_kakao
                ORDER BY count DESC NULLS LAST
                LIMIT 20
            """)
            print("TOP_CATEGORY_KAKAO", json.dumps(cur.fetchall(), ensure_ascii=False, default=str))


def searches() -> None:
    failures: list[str] = []
    for case in CASES:
        parsed = make_query(case)
        plan = build_restaurant_search_plan(
            parsed,
            parsed.tasks[0],
            current_lat=37.5665,
            current_lng=126.9780,
            current_location_name=None,
            top_n=10,
        )
        result = search_restaurants_structured(
            parsed,
            parsed.tasks[0],
            current_lat=37.5665,
            current_lng=126.9780,
            current_location_name=None,
            top_n=10,
        )
        summary = [{
            "name": c["name"],
            "category": c["category"],
            "category_status": c["breakdown"]["category_status"],
            "score": round(c["score"], 5),
            "distance_km": None if c["distance_km"] is None else round(c["distance_km"], 2),
            "open_status": c["open_status"],
            "rating": c["rating"],
            "menu_price_median": c.get("menu_price_median"),
        } for c in result["candidates"][:10]]
        print("CASE", case["label"])
        print("PLAN", json.dumps(plan.__dict__, ensure_ascii=False, default=str))
        print("RESULT", json.dumps(summary, ensure_ascii=False, default=str))

        candidates = result["candidates"]
        if not candidates:
            failures.append(f"{case['label']}: 결과 없음")
            continue
        if any(c.get("distance_km") is not None and c["distance_km"] > plan.radius_km + 0.01 for c in candidates):
            failures.append(f"{case['label']}: 반경 밖 후보 포함")
        if case.get("expected_category") and any(
            c["breakdown"]["category_status"] != "match" for c in candidates
        ):
            failures.append(f"{case['label']}: 음식 종류 불일치 후보 포함")
        if case.get("require_open") and any(c.get("open_status") is not True for c in candidates):
            failures.append(f"{case['label']}: 현재 영업 미확인 후보 포함")
        if case.get("require_visit_open") and any(c.get("open_status") is False for c in candidates):
            failures.append(f"{case['label']}: 방문 시각 휴무 후보 포함")
        if case.get("min_rating") is not None and any(
            c.get("rating") is None or c["rating"] < case["min_rating"] for c in candidates
        ):
            failures.append(f"{case['label']}: 최소 평점 위반")
        for field in plan.required_feature_fields:
            if any(c.get(field) is not True for c in candidates):
                failures.append(f"{case['label']}: 필수 시설 {field} 위반")
        if plan.budget_max_krw is not None and any(
            c.get("menu_price_median") is None
            or c["menu_price_median"] > plan.budget_max_krw
            for c in candidates
        ):
            failures.append(f"{case['label']}: 최대 예산 위반")

    if failures:
        print("AUDIT_FAILED", json.dumps(failures, ensure_ascii=False))
        raise SystemExit(1)
    print(f"AUDIT_OK {len(CASES)} cases")


if __name__ == "__main__":
    coverage()
    searches()
