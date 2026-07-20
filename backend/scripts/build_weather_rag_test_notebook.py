"""Create a clean, output-free notebook for manually testing the weather RAG flow."""

from __future__ import annotations

import ast
import json
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BACKEND_DIR / "weather_rag_manual_test.ipynb"


def markdown(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


cells = [
    markdown(
        """# SeoulMate 날씨 기반 식당 재랭킹 수동 테스트

이 노트북은 아래 흐름을 셀별로 직접 확인합니다.

1. 환경변수와 DB 상태 확인
2. 기상청 좌표 변환 및 실제 날씨 조회
3. RAG로 식당 후보 30개 검색
4. 날씨를 보조 신호로 재랭킹
5. 상위 10개를 근거로 GPT 최종 답변 생성

API 키 값은 출력하지 않고 **설정 여부만** 표시합니다.

### 실행 전 준비

- 터미널에서 `SeoulMate/backend`로 이동한 뒤 `uv sync`
- Jupyter 커널로 `SeoulMate/backend/.venv/Scripts/python.exe` 선택
- Windows 사용자 환경변수에 `KMA_API_KEY`, `OPENAI_API_KEY`, `KAKAO_REST_API_KEY` 설정
- PostgreSQL/pgvector 및 한글 식당·리뷰·메뉴 임베딩 테이블 실행

처음에는 위에서 아래로 실행하세요. 환경변수를 수정했다면 주피터를 완전히 재시작해야 합니다."""
    ),
    code(
        """from pathlib import Path
import os
import sys
import winreg
from pprint import pprint

from dotenv import load_dotenv

# 사용자 PC의 SeoulMate 백엔드 절대 경로
BACKEND_DIR = Path("C:/Users/user/Desktop/seoulmate/SeoulMate/backend")
if not (BACKEND_DIR / "services" / "rag.py").exists():
    raise FileNotFoundError(f"백엔드 절대 경로를 확인하세요: {BACKEND_DIR}")

# 이미 실행 중인 Jupyter도 Windows 사용자 환경변수를 읽을 수 있게 보완합니다.
def load_windows_user_environment(*names):
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


load_windows_user_environment(
    "KMA_API_KEY",
    "OPENAI_API_KEY",
    "KAKAO_REST_API_KEY",
)

# .env가 있으면 비어 있는 값만 보완하며 기존 환경변수는 덮어쓰지 않습니다.
load_dotenv(BACKEND_DIR / ".env", override=False)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

print("backend:", BACKEND_DIR)
print("python :", sys.executable)
print("env    : Windows 환경변수 우선 (.env는 선택 사항)")"""
    ),
    markdown(
        """## 1. 환경변수 확인

값 자체는 노출하지 않습니다. 첫 셀이 Windows 사용자 환경변수를 현재 커널로 불러옵니다.

- `KMA_API_KEY`: 기상청 날씨 조회
- `OPENAI_API_KEY`: 임베딩 검색과 GPT 답변
- `KAKAO_REST_API_KEY`: 질의에 지명이 있을 때 좌표 검색"""
    ),
    code(
        """required_keys = ["KMA_API_KEY", "OPENAI_API_KEY", "KAKAO_REST_API_KEY"]
optional_keys = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]

status = {key: bool(os.getenv(key)) for key in required_keys + optional_keys}
pprint(status)

missing_required = [key for key in required_keys if not status[key]]
if missing_required:
    print("\\n필수 키 미설정:", ", ".join(missing_required))
else:
    print("\\n필수 API 키가 모두 설정되어 있습니다.")"""
    ),
    markdown(
        """## 2. DB 연결과 테이블 건수 확인

비밀번호는 출력하지 않습니다. RAG 테스트에는 한글 원본 및 임베딩 테이블이 필요합니다."""
    ),
    code(
        """import psycopg2
from core.config import DB_CONFIG

table_names = [
    "restaurant_ko",
    "restaurant_embedding_ko",
    "review_embedding_ko",
    "menu_embedding_ko",
]

safe_db_info = {key: value for key, value in DB_CONFIG.items() if key != "password"}
print("DB 설정:", safe_db_info)

with psycopg2.connect(**DB_CONFIG) as connection:
    with connection.cursor() as cursor:
        counts = {}
        for table_name in table_names:
            cursor.execute("SELECT to_regclass(%s)", (table_name,))
            exists = cursor.fetchone()[0] is not None
            if exists:
                cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                counts[table_name] = cursor.fetchone()[0]
            else:
                counts[table_name] = "MISSING"

pprint(counts)"""
    ),
    markdown(
        """## 3. 외부 API 없이 재랭킹 로직만 빠르게 확인

가짜 후보와 비 오는 날씨를 넣어, 가까운 거리와 주차 가능 여부가 보조 점수에 반영되는지 봅니다."""
    ),
    code(
        """from copy import deepcopy
from services.weather import latlng_to_grid
from services.weather_reranker import rerank_with_weather

SEOUL_CITY_HALL = (37.5665, 126.9780)
print("서울시청 기상청 격자(nx, ny):", latlng_to_grid(*SEOUL_CITY_HALL))"""
    ),
    code(
        """# 로컬 로직 확인용 가짜 후보와 날씨
sample_candidates = [
    {
        "restaurant_id": 1,
        "name": "RAG 점수가 높은 식당",
        "score": 0.100,
        "distance_km": 1.8,
        "has_parking": False,
        "evidence": {"menus": [{"menu_name": "초밥"}]},
    },
    {
        "restaurant_id": 2,
        "name": "비 오는 날 가까운 식당",
        "score": 0.098,
        "distance_km": 0.3,
        "has_parking": True,
        "evidence": {"menus": [{"menu_name": "라멘"}]},
    },
]
sample_weather = {
    "available": True,
    "condition": "rain",
    "feels_like": "mild",
    "temperature_c": 18.0,
}"""
    ),
    code(
        """# 외부 API 호출 없이 날씨 재랭킹 실행
sample_result = rerank_with_weather(
    deepcopy(sample_candidates), sample_weather, "비 오는 날 식당 추천"
)
[
    {
        "rank": index,
        "name": item["name"],
        "final_score": round(item["score"], 4),
        "rag_score": item["rag_score"],
        "weather_score": item["weather_score"],
        "weather_reasons": item["weather_reasons"],
    }
    for index, item in enumerate(sample_result, start=1)
]"""
    ),
    markdown(
        """## 4. 실제 기상청 API 조회

기본 좌표는 서울시청입니다. `weather["available"]`이 `False`이면 `error` 내용을 확인하세요. 일반적으로 키 인코딩 방식, 승인 대기, 키 오타가 원인입니다."""
    ),
    code(
        """import importlib
import core.config as config_module
import services.weather as weather_module

# 이미 import된 모듈도 방금 읽은 환경변수를 사용하도록 갱신합니다.
importlib.reload(config_module)
importlib.reload(weather_module)
get_weather_context = weather_module.get_weather_context

if not os.getenv("KMA_API_KEY"):
    raise RuntimeError("KMA_API_KEY를 찾지 못했습니다. 첫 번째 셀부터 다시 실행하세요.")

weather = get_weather_context(*SEOUL_CITY_HALL)
pprint(weather)"""
    ),
    markdown(
        """## 5. 실제 RAG 후보 30개 검색

질의를 자유롭게 바꿔 실행하세요. 지명이 포함되면 카카오 로컬 API로 중심 좌표를 찾고, 설정한 반경 안에서 검색합니다."""
    ),
    code(
        """from services.rag import search_restaurants

QUERY = "홍대입구역 근처 비 오는 날 데이트하기 좋은 일식당"
LANG = "ko"
RADIUS_KM = 2.0
TOP_N = 30

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("RAG 임베딩 호출에 OPENAI_API_KEY가 필요합니다.")
if not os.getenv("KAKAO_REST_API_KEY"):
    raise RuntimeError("지명 좌표 검색에 KAKAO_REST_API_KEY가 필요합니다.")"""
    ),
    code(
        """# PostgreSQL/pgvector에서 후보 30개 검색
rag_result = search_restaurants(
    query=QUERY,
    lang=LANG,
    radius_km=RADIUS_KM,
    top_n=TOP_N,
)
candidates = rag_result["candidates"]"""
    ),
    code(
        """# 위치·카테고리 추출 결과 확인
print("검색 질의        :", QUERY)
print("추출 위치        :", rag_result["location_name"])
print("중심 좌표        :", rag_result["origin_lat"], rag_result["origin_lng"])
print("추출 카테고리    :", rag_result["extracted_category"])
print("임베딩 검색 문장 :", rag_result["cleaned_query"])
print("후보 수          :", len(candidates))

[
    {
        "rank": index,
        "id": item["restaurant_id"],
        "name": item["name"],
        "category": item["category"],
        "rating": item["rating"],
        "distance_km": None if item["distance_km"] is None else round(item["distance_km"], 2),
        "rag_score": round(item["score"], 6),
    }
    for index, item in enumerate(candidates, start=1)
]"""
    ),
    markdown(
        """## 6. 검색 위치의 실제 날씨로 30개 후보 재랭킹

질의에서 위치 좌표가 추출되면 그 좌표를 사용하고, 없으면 서울시청 좌표를 사용합니다. 날씨 API가 실패하면 원래 RAG 순서를 보존합니다."""
    ),
    code(
        """weather_lat = rag_result["origin_lat"] or SEOUL_CITY_HALL[0]
weather_lng = rag_result["origin_lng"] or SEOUL_CITY_HALL[1]
weather = get_weather_context(weather_lat, weather_lng)

print("날씨:")
pprint(weather)"""
    ),
    code(
        """# 후보 원본을 보존하기 위해 복사본을 재랭킹합니다.
reranked = rerank_with_weather(deepcopy(candidates), weather, QUERY)

print("재랭킹 상위 10개:")
[
    {
        "rank": index,
        "name": item["name"],
        "distance_km": None if item["distance_km"] is None else round(item["distance_km"], 2),
        "rag_score": round(item["rag_score"], 6),
        "weather_score": item["weather_score"],
        "final_score": round(item["score"], 6),
        "weather_reasons": item["weather_reasons"],
    }
    for index, item in enumerate(reranked[:10], start=1)
]"""
    ),
    markdown(
        """## 7. 재랭킹 전후 순위 비교"""
    ),
    code(
        """before_rank = {item["restaurant_id"]: index for index, item in enumerate(candidates, start=1)}

comparison = [
    {
        "after": after,
        "before": before_rank[item["restaurant_id"]],
        "change": before_rank[item["restaurant_id"]] - after,
        "name": item["name"],
        "rag_score": round(item["rag_score"], 6),
        "weather_score": item["weather_score"],
        "final_score": round(item["score"], 6),
    }
    for after, item in enumerate(reranked[:10], start=1)
]
comparison"""
    ),
    markdown(
        """## 8. GPT 최종 답변 생성

재랭킹 상위 10개만 GPT에 전달하고, GPT는 그 후보 안에서 최대 3곳을 추천합니다. 현재 구현과 동일하게 OpenAI Responses API를 호출합니다."""
    ),
    code(
        """from services.llm import generate_recommendation

if not reranked:
    raise RuntimeError("추천 후보가 없습니다. 앞 셀의 RAG 결과와 DB를 확인하세요.")

answer = generate_recommendation(
    message=QUERY,
    lang=LANG,
    candidates=reranked[:10],
    weather=weather,
)
print(answer)"""
    ),
    markdown(
        """## 9. 한 번에 재실행하는 함수

위 셀들이 정상 동작한 뒤, 여러 질의를 비교할 때 사용하세요."""
    ),
    code(
        """def run_full_pipeline(query: str, lang: str = "ko", radius_km: float = 2.0) -> dict:
    rag = search_restaurants(query=query, lang=lang, radius_km=radius_km, top_n=30)
    found = rag["candidates"]
    lat = rag["origin_lat"] or SEOUL_CITY_HALL[0]
    lng = rag["origin_lng"] or SEOUL_CITY_HALL[1]
    current_weather = get_weather_context(lat, lng)
    ranked = rerank_with_weather(deepcopy(found), current_weather, query)
    final_answer = (
        generate_recommendation(query, lang, ranked[:10], current_weather)
        if ranked
        else "조건에 맞는 식당 후보를 찾지 못했습니다."
    )
    return {
        "query": query,
        "location_name": rag["location_name"],
        "weather": current_weather,
        "candidate_count": len(found),
        "top_10": ranked[:10],
        "answer": final_answer,
    }


# 원하는 질의로 바꿔 실행하세요.
result = run_full_pipeline("강남역 근처 추운 날 따뜻한 국물 요리 추천")
print(result["answer"])
[
    (index, item["name"], round(item["score"], 6), item["weather_reasons"])
    for index, item in enumerate(result["top_10"], start=1)
]"""
    ),
    markdown(
        """## 오류가 날 때 확인할 것

- **API 키를 바꿨는데 그대로임**: 주피터 서버/VS Code를 완전히 재시작하고 1번 셀부터 다시 실행
- **KMA `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`**: 활용 신청 승인 상태와 일반 인증키(Encoding/Decoding)를 확인
- **카카오 401/403**: Kakao Developers 앱의 REST API 키인지 확인
- **DB connection refused**: PostgreSQL 포트가 `.env`의 `DB_PORT`와 같은지 확인
- **임베딩 차원 오류**: DB의 vector 차원과 `OPENAI_EMBED_DIM`이 같은지 확인
- **후보 0개**: 위치 반경을 늘리거나, 해당 언어의 원본/임베딩 테이블 건수를 확인"""
    ),
]


notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "SeoulMate backend (.venv)",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.12",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUTPUT_PATH.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
for index, cell in enumerate(cells):
    if cell["cell_type"] == "code":
        ast.parse("".join(cell["source"]), filename=f"cell-{index}")
assert all(not cell.get("outputs") for cell in cells if cell["cell_type"] == "code")
print(OUTPUT_PATH)
