"""실제 Parser → 식당 RAG → Weather MCP → 최종 GPT 20문항 노트북 생성."""

from pathlib import Path

import nbformat as nbf


BACKEND = Path(__file__).resolve().parents[1]
OUTPUT = BACKEND / "notebooks" / "SeoulMate_rag_mcp_20q_livedb_test.ipynb"

nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell("""# SeoulMate 단일 선택 20문항 실제 E2E 검증

각 질문을 다음 운영 경로로 검증합니다.

1. 실제 `gpt-4o-mini` Structured Query Parser
2. 실제 PostgreSQL 식당·리뷰·메뉴 벡터 검색과 RRF
3. `rag_mcp` 질문만 실제 Weather MCP 호출 및 식당 날씨 재랭킹
4. 재랭킹 상위 10개를 실제 최종 GPT에 전달
5. GPT가 선택한 최대 3개 ID, 이유, 답변을 서버 검증기로 재검증

카페·숙박·문화시설은 이 노트북의 범위가 아닙니다. 모든 질문은 식당 단일 선택입니다.
원본 후보가 0개인 경우에는 GPT를 호출하지 않고 명시적인 조건 완화 안내를 검증합니다.
"""))

cells.append(nbf.v4.new_markdown_cell("## 1. 절대 경로·환경·실행 플래그"))
cells.append(nbf.v4.new_code_cell(r'''import os, sys, json, copy, asyncio, subprocess, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
from IPython.display import display

BACKEND_DIR = Path(r"C:\Users\user\Desktop\seoulmate\SeoulMate\backend")
if not (BACKEND_DIR / "services" / "rag.py").exists():
    raise RuntimeError(f"backend 절대 경로가 올바르지 않습니다: {BACKEND_DIR}")
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env", override=False)

RUN_LIVE_QUERY_PARSER = True
RUN_LIVE_FINAL_GPT = True
PARSER_MODEL = "gpt-4o-mini"
RAG_CANDIDATE_COUNT = 30
GPT_CANDIDATE_COUNT = 10
CURRENT_LAT, CURRENT_LNG = 37.5665, 126.9780
CURRENT_LOCATION_NAME = "서울시청"

assert os.getenv("OPENAI_API_KEY"), ".env에 OPENAI_API_KEY가 필요합니다."
pd.set_option("display.max_colwidth", 70)
print("backend:", BACKEND_DIR)
print("python:", sys.executable)
print("parser:", PARSER_MODEL)
print("live parser/final GPT:", RUN_LIVE_QUERY_PARSER, RUN_LIVE_FINAL_GPT)'''))

cells.append(nbf.v4.new_markdown_cell("## 2. 실제 PostgreSQL·Weather MCP 준비"))
cells.append(nbf.v4.new_code_cell(r'''import psycopg2
from core.config import DB_CONFIG, OPENAI_CHAT_MODEL

with psycopg2.connect(**DB_CONFIG) as connection:
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
              (SELECT COUNT(*) FROM restaurant_ko),
              (SELECT COUNT(*) FROM restaurant_review_ko),
              (SELECT COUNT(*) FROM restaurant_menu_ko)
        """)
        DB_COUNTS = cursor.fetchone()
assert all(value > 0 for value in DB_COUNTS)
print({"restaurant_ko": DB_COUNTS[0], "review_ko": DB_COUNTS[1], "menu_ko": DB_COUNTS[2]})
print("final GPT model:", OPENAI_CHAT_MODEL)

WEATHER_MCP_URL = os.getenv("WEATHER_MCP_URL", "http://127.0.0.1:8001/mcp")
HEALTH_URL = WEATHER_MCP_URL.rsplit("/mcp", 1)[0] + "/health"
MCP_PROCESS = None

def weather_health():
    try:
        with urlopen(HEALTH_URL, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

health = weather_health()
if not health:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    MCP_PROCESS = subprocess.Popen(
        [sys.executable, str(BACKEND_DIR / "weather_mcp_server.py")],
        cwd=BACKEND_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    for _ in range(30):
        time.sleep(1)
        health = weather_health()
        if health:
            break
if not health:
    raise RuntimeError("Weather MCP 서버를 준비하지 못했습니다.")
print("weather health:", health)'''))

cells.append(nbf.v4.new_markdown_cell("## 3. 식당 단일 선택 질문 20개"))
cells.append(nbf.v4.new_code_cell(r'''TOMORROW = date.today() + timedelta(days=1)

CASES = [
    {"id": 1, "question": "홍대에서 중식당 추천해줘", "category": "중국 요리", "nonempty": True},
    {"id": 2, "question": "홍대에서 조용하고 대화하기 좋은 중식당 추천해줘", "category": "중국 요리", "nonempty": True},
    {"id": 3, "question": "홍대에서 떡볶이 파는 식당 추천해줘", "menu_term": "떡볶이", "nonempty": True},
    {"id": 4, "question": "홍대에서 평점 4.0 이상인 중식당 추천해줘", "category": "중국 요리", "min_rating": 4.0, "nonempty": True},
    {"id": 5, "question": "홍대에서 주차 가능한 중식당 추천해줘", "category": "중국 요리", "feature": "has_parking", "nonempty": True},
    {"id": 6, "question": "강남에서 룸이 있는 스테이크 식당 추천해줘", "category": "스테이크하우스", "feature": "has_private_room"},
    {"id": 7, "question": "강남에서 1인 메뉴 중앙가격 3만원 이하인 일식당 추천해줘", "category": "일본 요리", "budget_max": 30000, "nonempty": True},
    {"id": 8, "question": "강남에서 키즈 메뉴가 있는 이탈리안 식당 추천해줘", "category": "이탈리아 요리", "feature": "has_kids_menu"},
    {"id": 9, "question": "종로에서 휠체어 접근 가능한 한식당 추천해줘", "category": "한국", "feature": "has_disabled_access", "nonempty": True},
    {"id": 10, "question": "Find a Chinese restaurant in Hongdae.", "category": "중국 요리", "language": "en", "nonempty": True},
    {"id": 11, "question": "Find a restaurant easily accessible from Hongdae station.", "forbidden_feature": "has_disabled_access", "language": "en", "nonempty": True},
    {"id": 12, "question": "이태원에서 태국 음식점 추천해줘", "category": "타이 요리", "nonempty": True},
    {"id": 13, "question": "강남에서 단체 회식 가능한 고깃집 추천해줘", "category": "바베큐", "feature": "has_group_seating", "nonempty": True},
    {"id": 14, "question": "홍대 맛집 추천해줘", "category": None, "nonempty": True},
    {"id": 15, "question": "홍대 반경 1km 안의 중식당 추천해줘", "category": "중국 요리", "radius": 1.0, "nonempty": True},
    {"id": 16, "question": "홍대에서 평점 좋은 중식당 추천해줘", "category": "중국 요리", "nonempty": True},
    {"id": 17, "question": "강남에서 브런치 먹기 좋은 식당 추천해줘", "nonempty": True},
    {"id": 18, "question": "종로에서 회나 물회를 잘하는 해산물 식당 추천해줘", "category": "해산물"},
    {"id": 19, "question": "내일 저녁 비가 오면 홍대에서 가기 좋은 중식당 추천해줘", "category": "중국 요리", "source_mode": "rag_mcp", "nonempty": True},
    {"id": 20, "question": "오늘 날씨가 더운데 이태원에서 쌀국수 먹을 식당 추천해줘", "source_mode": "rag_mcp", "nonempty": True},
]
assert len(CASES) == 20
display(pd.DataFrame(CASES)[["id", "question"]])'''))

cells.append(nbf.v4.new_markdown_cell("## 4. 실제 gpt-4o-mini Structured Query Parser"))
cells.append(nbf.v4.new_code_cell(r'''from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from schemas.structured_query import StructuredTravelQuery
from scripts.audit_question_to_rag import PARSER_HUMAN_PROMPT, PARSER_SYSTEM_PROMPT

parser_chain = (
    ChatPromptTemplate.from_messages([
        ("system", PARSER_SYSTEM_PROMPT),
        ("human", PARSER_HUMAN_PROMPT),
    ])
    | ChatOpenAI(model=PARSER_MODEL, temperature=0).with_structured_output(
        StructuredTravelQuery,
        method="function_calling",
    )
)
USER_CONTEXT = {
    "current_location": {"latitude": CURRENT_LAT, "longitude": CURRENT_LNG},
    "location_name": CURRENT_LOCATION_NAME,
    "timezone": "Asia/Seoul",
}

PARSED = {}
PARSER_ERRORS = {}
for cs in CASES:
    try:
        if not RUN_LIVE_QUERY_PARSER:
            raise RuntimeError("RUN_LIVE_QUERY_PARSER=False")
        PARSED[cs["id"]] = parser_chain.invoke({
            "today": date.today().isoformat(),
            "user_context": json.dumps(USER_CONTEXT, ensure_ascii=False),
            "question": cs["question"],
        })
    except Exception as exc:
        PARSER_ERRORS[cs["id"]] = f"{type(exc).__name__}: {exc}"

parser_rows = []
for cs in CASES:
    parsed = PARSED.get(cs["id"])
    restaurant_tasks = [t for t in parsed.tasks if t.domain == "restaurant"] if parsed else []
    parser_rows.append({
        "id": cs["id"],
        "intent": parsed.intent if parsed else None,
        "source_mode": parsed.source_mode if parsed else None,
        "language": parsed.language if parsed else None,
        "restaurant_tasks": len(restaurant_tasks),
        "search_query": restaurant_tasks[0].search_query if restaurant_tasks else None,
        "error": PARSER_ERRORS.get(cs["id"]),
    })
display(pd.DataFrame(parser_rows))
print("parser 성공:", len(PARSED), "/", len(CASES))'''))

cells.append(nbf.v4.new_markdown_cell("## 5. 실제 RAG·MCP·최종 GPT 실행"))
cells.append(nbf.v4.new_code_cell(r'''from domains.restaurant.search_plan import build_restaurant_search_plan
from domains.restaurant.vector_search import search_restaurants_structured
from domains.restaurant.weather_policy import prepare_rag_only_candidates, rerank_with_weather
from integrations.mcp.weather_client import get_weather_via_mcp
from services.llm import generate_recommendation_result
from services.query_policy import derive_source_mode, effective_query_language
from scripts.audit_question_to_rag import _candidate_violations

def run_coro(coro):
    # Jupyter가 이미 asyncio loop를 실행하는 경우에도 안전하게 별도 thread에서 수행한다.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()

TRACE = {}
SUMMARY = []
for cs in CASES:
    cid = cs["id"]
    parsed = PARSED.get(cid)
    errors, warnings = [], []
    if parsed is None:
        SUMMARY.append({"id": cid, "status": "FAIL", "errors": PARSER_ERRORS.get(cid)})
        continue
    tasks = [task for task in parsed.tasks if task.domain == "restaurant"]
    if parsed.intent != "single_place_recommendation":
        errors.append(f"intent={parsed.intent}")
    if len(tasks) != 1:
        errors.append(f"restaurant task count={len(tasks)}")
    if not tasks:
        SUMMARY.append({"id": cid, "status": "FAIL", "errors": "; ".join(errors)})
        continue
    task = tasks[0]
    mode = derive_source_mode(parsed)
    plan = build_restaurant_search_plan(
        parsed, task,
        current_lat=CURRENT_LAT,
        current_lng=CURRENT_LNG,
        current_location_name=CURRENT_LOCATION_NAME,
        top_n=RAG_CANDIDATE_COUNT,
    )
    result = search_restaurants_structured(
        parsed, task,
        current_lat=CURRENT_LAT,
        current_lng=CURRENT_LNG,
        current_location_name=CURRENT_LOCATION_NAME,
        top_n=RAG_CANDIDATE_COUNT,
    )
    raw_candidates = copy.deepcopy(result["candidates"])
    violations = {
        str(item["restaurant_id"]): _candidate_violations(item, plan)
        for item in raw_candidates
        if _candidate_violations(item, plan)
    }
    if violations:
        errors.append(f"hard-filter violations={violations}")

    expected_category = cs.get("category", "__unspecified__")
    if expected_category != "__unspecified__" and plan.requested_category != expected_category:
        errors.append(f"category expected={expected_category!r}, actual={plan.requested_category!r}")
    if cs.get("feature") and cs["feature"] not in plan.required_feature_fields:
        errors.append(f"missing required feature={cs['feature']}")
    if cs.get("forbidden_feature") in plan.required_feature_fields:
        errors.append(f"false-positive feature={cs['forbidden_feature']}")
    if cs.get("min_rating") is not None and plan.min_rating != cs["min_rating"]:
        errors.append(f"min_rating={plan.min_rating}")
    if cs.get("budget_max") is not None and plan.budget_max_krw != cs["budget_max"]:
        errors.append(f"budget_max={plan.budget_max_krw}")
    if cs.get("radius") is not None and abs(plan.radius_km - cs["radius"]) > 1e-6:
        errors.append(f"radius={plan.radius_km}")
    if cs.get("menu_term") and cs["menu_term"] not in plan.required_menu_terms:
        errors.append(f"required_menu_terms={plan.required_menu_terms}")
    if cs.get("source_mode") and mode != cs["source_mode"]:
        errors.append(f"source_mode={mode}")
    if cs.get("language") and effective_query_language(parsed) != cs["language"]:
        errors.append(f"effective_language={effective_query_language(parsed)}")
    if cs.get("nonempty") and not raw_candidates:
        errors.append("expected candidates but got 0")

    weather = None
    if mode == "rag_mcp":
        wr = parsed.weather_request
        weather = run_coro(get_weather_via_mcp(
            query=(wr.query if wr else parsed.original_question),
            lat=plan.origin_lat or CURRENT_LAT,
            lng=plan.origin_lng or CURRENT_LNG,
            language=effective_query_language(parsed),
            place_name=plan.location_name,
            target_date=(str(wr.target_date) if wr and wr.target_date else None),
            target_time=(wr.target_time if wr else None),
        ))
        if not weather.get("available"):
            errors.append(f"Weather MCP unavailable: {weather.get('error')}")
        final_candidates = rerank_with_weather(
            copy.deepcopy(raw_candidates), weather, parsed.original_question, source_mode="rag_mcp"
        )
    else:
        final_candidates = prepare_rag_only_candidates(copy.deepcopy(raw_candidates))
        if any(item.get("weather_score") is not None for item in final_candidates):
            errors.append("rag_only에 weather_score가 남음")

    pool = final_candidates[:GPT_CANDIDATE_COUNT]
    if RUN_LIVE_FINAL_GPT:
        final = generate_recommendation_result(
            parsed.original_question,
            effective_query_language(parsed),
            pool,
            weather=weather,
            source_mode=mode,
            structured_context=parsed.model_dump(mode="json"),
        )
    else:
        final = {"answer": "SKIPPED", "selections": [], "llm_fallback_used": True, "repaired": False}

    allowed_ids = {str(item["restaurant_id"]) for item in pool}
    selected_ids = [str(item["candidate"]["restaurant_id"]) for item in final["selections"]]
    reasons = [str(item.get("selection_reason") or "") for item in final["selections"]]
    expected_count = min(3, len(pool))
    if len(selected_ids) != expected_count:
        errors.append(f"selection count={len(selected_ids)}, expected={expected_count}")
    if len(selected_ids) != len(set(selected_ids)):
        errors.append("duplicate final IDs")
    if not set(selected_ids).issubset(allowed_ids):
        errors.append("GPT selected an ID outside top-10 whitelist")
    if any(not reason.strip() for reason in reasons):
        errors.append("empty selection_reason")
    internal_terms = ("rrf", "weather_score", "rag_score", "has_parking", "vector")
    if any(term in (final.get("answer", "") + " " + " ".join(reasons)).lower() for term in internal_terms):
        errors.append("internal implementation term leaked")
    if not pool and not final.get("no_candidates"):
        errors.append("empty pool did not use no_candidates response")
    if pool and final.get("llm_fallback_used"):
        warnings.append("final GPT API fallback used")
    if final.get("repaired"):
        warnings.append("final GPT output repaired by server whitelist")

    raw_order = [str(item["restaurant_id"]) for item in raw_candidates]
    final_order = [str(item["restaurant_id"]) for item in final_candidates]
    TRACE[cid] = {
        "case": cs,
        "parsed": parsed,
        "task": task,
        "mode": mode,
        "plan": plan,
        "rag_result": result,
        "raw_candidates": raw_candidates,
        "final_candidates": final_candidates,
        "weather": weather,
        "final": final,
        "errors": errors,
        "warnings": warnings,
    }
    SUMMARY.append({
        "id": cid,
        "status": "PASS" if not errors else "FAIL",
        "mode": mode,
        "category": plan.requested_category,
        "rag_count": len(raw_candidates),
        "rank_changed": raw_order != final_order,
        "selected": ", ".join(item["candidate"]["name"] for item in final["selections"]),
        "fallback": bool(final.get("llm_fallback_used")),
        "repaired": bool(final.get("repaired")),
        "warnings": "; ".join(warnings),
        "errors": "; ".join(errors),
    })

print("실제 20문항 파이프라인 실행 완료")'''))

cells.append(nbf.v4.new_markdown_cell("## 6. 전체 판정과 실패 원인"))
cells.append(nbf.v4.new_code_cell(r'''summary_df = pd.DataFrame(SUMMARY)
display(summary_df)
passed = int((summary_df["status"] == "PASS").sum())
print(f"PASS {passed}/20, FAIL {20-passed}/20")

failed = summary_df[summary_df["status"] == "FAIL"]
if not failed.empty:
    print("\n실패 상세")
    for row in failed.to_dict("records"):
        print(f"#{row['id']}: {row['errors']}")

print("\n서버 보정/외부 실패 경고")
warned = summary_df[summary_df["warnings"] != ""]
if warned.empty:
    print("없음")
else:
    display(warned[["id", "warnings"]])'''))

cells.append(nbf.v4.new_markdown_cell("## 7. 질문별 RAG 입력·전체 순위·날씨 순위·GPT 선택 이유"))
cells.append(nbf.v4.new_code_cell(r'''SHOW = list(range(1, 21))  # 필요한 ID만 남겨도 됩니다.

for cid in SHOW:
    trace = TRACE.get(cid)
    if not trace:
        print(f"#{cid}: trace 없음")
        continue
    plan = trace["plan"]
    print("=" * 110)
    print(f"#{cid} {trace['case']['question']}")
    print("mode=", trace["mode"], "retrieval=", repr(plan.retrieval_query),
          "review=", repr(plan.review_query), "menu=", repr(plan.menu_query))
    print("location=", plan.location_name, "radius=", plan.radius_km,
          "category=", plan.requested_category, "features=", plan.required_feature_fields,
          "budget=", (plan.budget_min_krw, plan.budget_max_krw))
    if trace["weather"]:
        w = trace["weather"]
        print("weather=", {k: w.get(k) for k in (
            "available", "target_label", "forecast_for", "condition", "temperature_c",
            "precipitation_probability_pct", "wind_speed_mps", "source"
        )})

    final_rank = {str(item["restaurant_id"]): rank for rank, item in enumerate(trace["final_candidates"], 1)}
    selected_reason = {
        str(item["candidate"]["restaurant_id"]): item["selection_reason"]
        for item in trace["final"]["selections"]
    }
    rows = []
    for rank, item in enumerate(trace["raw_candidates"], 1):
        rid = str(item["restaurant_id"])
        reranked = next((x for x in trace["final_candidates"] if str(x["restaurant_id"]) == rid), item)
        rows.append({
            "RAG순위": rank,
            "최종순위": final_rank.get(rid),
            "id": rid,
            "이름": item["name"],
            "RAG점수": round(float(item.get("score") or 0), 5),
            "날씨점수": reranked.get("weather_score"),
            "최종점수": round(float(reranked.get("score") or 0), 5),
            "평점": item.get("rating"),
            "거리km": item.get("distance_km"),
            "선택": rid in selected_reason,
            "선정이유": selected_reason.get(rid, ""),
            "날씨이유": " / ".join(reranked.get("weather_reasons") or []),
        })
    display(pd.DataFrame(rows))
    print("최종 답변:", trace["final"]["answer"])
    if trace["errors"]:
        print("ERRORS:", trace["errors"])
    if trace["warnings"]:
        print("WARNINGS:", trace["warnings"])'''))

cells.append(nbf.v4.new_markdown_cell("## 8. 자동 발견 개선사항"))
cells.append(nbf.v4.new_code_cell(r'''issues = []
zero_cases = [row["id"] for row in SUMMARY if row.get("rag_count") == 0]
fallback_cases = [row["id"] for row in SUMMARY if row.get("fallback")]
repaired_cases = [row["id"] for row in SUMMARY if row.get("repaired")]
failed_cases = [row["id"] for row in SUMMARY if row.get("status") == "FAIL"]
if zero_cases:
    issues.append(f"엄격한 조건으로 후보 0개: {zero_cases} — 조건 완화 UX 필요")
if fallback_cases:
    issues.append(f"최종 GPT API fallback: {fallback_cases}")
if repaired_cases:
    issues.append(f"GPT ID/개수/이유를 서버가 보정: {repaired_cases}")
if failed_cases:
    issues.append(f"계약 또는 필터 실패: {failed_cases}")
if not issues:
    issues.append("자동 계약 검사에서 중대한 문제를 찾지 못했습니다. 상세 선정 이유는 사람이 추가 검토하세요.")
for issue in issues:
    print("-", issue)'''))

cells.append(nbf.v4.new_markdown_cell("## 9. MCP 정리"))
cells.append(nbf.v4.new_code_cell(r'''if MCP_PROCESS is not None:
    MCP_PROCESS.terminate()
    try:
        MCP_PROCESS.wait(timeout=10)
    except subprocess.TimeoutExpired:
        MCP_PROCESS.kill()
    print("노트북이 시작한 Weather MCP를 종료했습니다.")
else:
    print("기존 Weather MCP를 사용했으므로 종료하지 않았습니다.")
print("DONE")'''))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3.12 (eduvenv)",
        "language": "python",
        "name": "eduenv",
    },
    "language_info": {"name": "python", "version": "3.12"},
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, OUTPUT)
print(OUTPUT)
