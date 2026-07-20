"""여러 질의로 RAG → 날씨 재랭킹 → GPT 답변을 반복 평가한다."""

from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_windows_user_environment(*names: str) -> None:
    if os.name != "nt":
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as registry_key:
        for name in names:
            if os.getenv(name):
                continue
            try:
                value, _ = winreg.QueryValueEx(registry_key, name)
            except FileNotFoundError:
                continue
            if value:
                os.environ[name] = str(value)


_load_windows_user_environment("OPENAI_API_KEY", "KAKAO_REST_API_KEY", "KMA_API_KEY")

from services.llm import generate_recommendation
from services.location import SEOUL_CENTER
from services.rag import search_restaurants
from services.weather import get_weather_for_query
from services.weather_reranker import rerank_with_weather


SCENARIOS = [
    {
        "name": "actual_hot_korean",
        "query": "강남역 근처 더운 날 시원한 메뉴가 있는 한식당 추천",
        "weather": "actual",
    },
    {
        "name": "actual_general_japanese",
        "query": "홍대입구역 근처 데이트하기 좋은 일식당 추천",
        "weather": "actual",
    },
    {
        "name": "actual_today_night",
        "query": "강남역 근처 오늘 밤 9시에 가기 좋은 한식당 추천",
        "weather": "actual",
    },
    {
        "name": "actual_tomorrow_dinner",
        "query": "강남역 근처 내일 가기 좋은 한식당 추천",
        "weather": "actual",
    },
    {
        "name": "synthetic_rain_wind",
        "query": "홍대입구역 근처 비바람이 강한 날 이동하기 편한 식당 추천",
        "weather": {
            "available": True,
            "condition": "rain",
            "temperature_c": 17.0,
            "humidity_pct": 92.0,
            "rainfall_mm": 8.0,
            "wind_speed_mps": 8.5,
            "feels_like": "mild",
            "source": "synthetic-test",
        },
    },
    {
        "name": "synthetic_cold_soup",
        "query": "종로3가역 근처 추운 날 따뜻한 국물 요리가 있는 한식당 추천",
        "weather": {
            "available": True,
            "condition": "clear",
            "temperature_c": 1.0,
            "humidity_pct": 45.0,
            "rainfall_mm": 0.0,
            "wind_speed_mps": 2.0,
            "feels_like": "cold",
            "source": "synthetic-test",
        },
    },
]


def _ranked_rows(before: list[dict], after: list[dict]) -> list[dict]:
    before_rank = {item["restaurant_id"]: index for index, item in enumerate(before, 1)}
    rows = []
    for after_rank, item in enumerate(after[:10], 1):
        feature = item.get("weather_features") or {}
        rows.append({
            "after_rank": after_rank,
            "before_rank": before_rank[item["restaurant_id"]],
            "rank_change": before_rank[item["restaurant_id"]] - after_rank,
            "restaurant_id": item["restaurant_id"],
            "name": item["name"],
            "rag_score": round(float(item.get("rag_score", item["score"])), 6),
            "final_score": round(float(item["score"]), 6),
            "weather_score": item.get("weather_score"),
            "distance_km": None if item.get("distance_km") is None else round(item["distance_km"], 3),
            "has_parking": item.get("has_parking"),
            "outdoor_confidence": item.get("outdoor_confidence"),
            "warm_menu_matches": feature.get("warm_menu_matches", []),
            "cool_menu_matches": feature.get("cool_menu_matches", []),
            "weather_reasons": item.get("weather_reasons", []),
        })
    return rows


def _checks(candidates: list[dict], rows: list[dict], weather: dict, answer: str) -> dict:
    condition = weather.get("condition")
    temperature = weather.get("temperature_c")
    all_reasons = [reason for row in rows for reason in row["weather_reasons"]]
    top_names = [row["name"] for row in rows]
    internal_terms = ("weather_", "RAG 점수", "weather 점수", "후보 데이터")
    return {
        "candidate_count_is_30": len(candidates) == 30,
        "all_candidates_have_weather_features": all("weather_features" in item for item in candidates),
        "description_is_connected": any(
            item.get("description") or item.get("description_kakao") for item in candidates
        ),
        "ranking_changed": any(row["rank_change"] != 0 for row in rows),
        "hot_menu_reason_present": (
            temperature is None or temperature < 28
            or any("시원한 메뉴" in reason for reason in all_reasons)
        ),
        "cold_menu_reason_present": (
            temperature is None or temperature >= 5
            or any("따뜻한 메뉴" in reason for reason in all_reasons)
        ),
        "rain_mobility_reason_present": (
            condition not in {"rain", "snow"}
            or any(any(word in reason for word in ("거리", "주차", "도보", "강풍")) for reason in all_reasons)
        ),
        "answer_mentions_shortlisted_restaurant": (
            any(name in answer for name in top_names) if answer else None
        ),
        "answer_hides_internal_terms": (
            not any(term in answer for term in internal_terms) if answer else None
        ),
    }


def run_scenario(scenario: dict, with_gpt: bool) -> dict:
    rag = search_restaurants(scenario["query"], lang="ko", radius_km=2.0, top_n=30)
    before = deepcopy(rag["candidates"])
    lat = rag.get("origin_lat") or SEOUL_CENTER[0]
    lng = rag.get("origin_lng") or SEOUL_CENTER[1]
    weather_spec = scenario["weather"]
    weather = get_weather_for_query(scenario["query"], lat, lng) if weather_spec == "actual" else {
        **weather_spec,
        "location": {"lat": lat, "lng": lng},
    }
    reranked = rerank_with_weather(deepcopy(before), weather, scenario["query"])
    rows = _ranked_rows(before, reranked)
    answer = (
        generate_recommendation(scenario["query"], "ko", reranked[:10], weather)
        if with_gpt and reranked
        else ""
    )
    return {
        "name": scenario["name"],
        "query": scenario["query"],
        "location_name": rag.get("location_name"),
        "origin": {"lat": lat, "lng": lng},
        "weather": weather,
        "candidate_count": len(before),
        "top_10": rows,
        "answer": answer,
        "checks": _checks(before, rows, weather, answer),
    }


def _markdown(results: list[dict]) -> str:
    lines = ["# SeoulMate 날씨 재랭킹 평가", ""]
    for result in results:
        weather = result["weather"]
        lines.extend([
            f"## {result['name']}",
            "",
            f"- 질의: {result['query']}",
            f"- 위치: {result['location_name']} ({result['origin']['lat']}, {result['origin']['lng']})",
            f"- 적용 시점: {weather.get('target_label') or '현재'} ({weather.get('forecast_for') or '-'})",
            f"- 날씨: {weather.get('source')} / {weather.get('condition')} / "
            f"{weather.get('temperature_c')}°C / 강수확률 {weather.get('precipitation_probability_pct')}% / "
            f"풍속 {weather.get('wind_speed_mps')}m/s",
            f"- 후보: {result['candidate_count']}개",
            "",
            "|재랭킹|기존|변화|식당|RAG|최종|날씨 근거|",
            "|---:|---:|---:|---|---:|---:|---|",
        ])
        for row in result["top_10"]:
            reason = " / ".join(row["weather_reasons"]).replace("|", "\\|") or "-"
            lines.append(
                f"|{row['after_rank']}|{row['before_rank']}|{row['rank_change']:+d}|"
                f"{row['name']}|{row['rag_score']:.6f}|{row['final_score']:.6f}|{reason}|"
            )
        lines.extend(["", "### 자동 점검", "", "```json", json.dumps(result["checks"], ensure_ascii=False, indent=2), "```", ""])
        if result["answer"]:
            lines.extend(["### GPT 답변", "", result["answer"], ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-gpt", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND_DIR / "weather_rerank_evaluation.json",
    )
    args = parser.parse_args()

    results = []
    for scenario in SCENARIOS:
        print(f"running: {scenario['name']}", flush=True)
        results.append(run_scenario(scenario, args.with_gpt))

    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(_markdown(results), encoding="utf-8")
    print(args.output)
    print(markdown_path)


if __name__ == "__main__":
    main()
