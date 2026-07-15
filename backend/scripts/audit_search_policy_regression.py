# -*- coding: utf-8 -*-
"""패치 검증: 버그 재현 케이스는 고쳐졌고, 기존 정상 동작은 유지되는가."""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schemas.structured_query import StructuredTravelQuery, StructuredQueryTask
from services.query_policy import (
    infer_task_location, effective_task_filters, build_semantic_query,
    build_menu_query, explicit_feature_fields, structured_feature_fields,
)
from services import rag

FAIL = []
def check(label, actual, expected):
    ok = actual == expected
    print(f"  {'PASS' if ok else 'FAIL'} | {label}\n         got={actual!r} want={expected!r}")
    if not ok: FAIL.append(label)

def q(question, tasks=None, filters=None):
    return StructuredTravelQuery(
        intent="single_place_recommendation",
        original_question=question, normalized_question=question,
        tasks=tasks or [], filters=filters or {},
    )

print("\n=== [1] _clean_base_query 문자 절단 버그 (임베딩 쿼리 보존) ===")
for raw, loc, want in [
    ("홍대 떡볶이 맛집", "홍대", "떡볶이 맛집"),                              # 기존: '떡볶' 으로 잘림
    ("강남 곱창구이 잘하는 곳", "강남", "곱창구이 잘하는 곳"),                 # 기존: '곱창구' 로 잘림
    ("홍대 평점 4.5 이상이고 주차 가능한 한식당", "홍대", "주차 가능한 한식당"),  # 원래 의도(연결어미 제거) 보존
    ("강남 5만원 이하이고 조용한 중식당", "강남", "조용한 중식당"),
]:
    t = StructuredQueryTask(task_id="t1", domain="restaurant", search_query=raw)
    p = q(raw, [t], {"location": loc})
    f = effective_task_filters(p, t)
    check(f"semantic({raw})", build_semantic_query(t, f), want)

print("\n=== [2] 지역 추론: '서울 홍대' → 홍대 (광역으로 오인 금지) ===")
for sq, want in [("서울 홍대 조용한 카페", "홍대"), ("홍대 조용한 카페", "홍대"),
                 ("서울 강남 파스타집", "강남"), ("서울에서 성수 감성 카페", "성수"),
                 ("역삼동 조용한 카페", "역삼동"), ("강남역 근처 한식당", "강남"),
                 ("서울 맛집 추천", "서울"), ("운동하고 먹을 식당", None),
                 ("친구랑 갈 식당", None), ("조용한 카페", None)]:
    check(f"infer({sq})", infer_task_location(sq), want)

print("\n=== [3] 다중 Task 지역 상속 (전역 홍대를 역삼동 Task가 상속하면 안 됨) ===")
t_r = StructuredQueryTask(task_id="t1", domain="restaurant", search_query="홍대 조용한 식당")
t_c = StructuredQueryTask(task_id="t2", domain="cafe", search_query="역삼동 분위기 좋은 카페")
p = q("홍대에서 식당, 역삼동에서 카페 추천해줘", [t_r, t_c], {"location": "홍대"})
check("restaurant task location", effective_task_filters(p, t_r).location, "홍대")
check("cafe task location", effective_task_filters(p, t_c).location, "역삼동")

print("\n=== [4] 시설 조건 오탐 제거 (하드 필터) ===")
cases = [
    ("Find a cafe easily accessible from Hongdae Station.", ()),
    ("Any restaurant in groups of friends style, casual vibe?", ()),
    ("홍대 플레이룸 근처 조용한 식당", ()),
    ("주차 가능한 한식당", ("has_parking",)),
    ("Wheelchair accessible Chinese restaurant", ("has_disabled_access",)),
    ("룸 있는 중식당 추천해줘", ("has_private_room",)),
    ("단체석 있는 고깃집", ("has_group_seating",)),
    ("주차는 없어도 괜찮아. 평점 좋은 태국 음식점 추천해줘.", ()),
    ("반려동물 동반 가능한 카페", ("allows_pets",)),
]
for question, want in cases:
    check(f"features({question[:34]})", explicit_feature_fields(q(question)), want)
check("structured(['주차','휠체어'])", structured_feature_fields(["주차", "휠체어"]),
      ("has_parking", "has_disabled_access"))

print("\n=== [5] 평점 선호가 관련도를 덮어쓰지 않는가 ===")
cands = [
    {"restaurant_id":1,"name":"관련도 최상 인기집","base":0.0400,"rating":4.4,"reviews":1200},
    {"restaurant_id":2,"name":"관련도 중간",      "base":0.0200,"rating":4.6,"reviews":300},
    {"restaurant_id":3,"name":"관련도 최하 신규집","base":0.0010,"rating":5.0,"reviews":2},
]
for prefer in (False, True):
    scored = []
    for c in cands:
        boost = rag._rating_preference_boost(c["base"], c["rating"], c["reviews"], prefer)
        scored.append({**c, "score": c["base"] + boost, "open_status": True})
    scored.sort(key=lambda i: (0, -i["score"], -(i["reviews"] or 0), i["restaurant_id"]))
    order = [i["name"] for i in scored]
    print(f"  prefer_high_rating={prefer}: {order}")
    if prefer:
        check("평점선호 시에도 관련도 최상이 1위", order[0], "관련도 최상 인기집")
        check("리뷰 2개 5.0점이 꼴찌 유지", order[-1], "관련도 최하 신규집")

print("\n=== [6] 카테고리 선별 + no_match 플래그 ===")
def c(i, status): return {"restaurant_id": i, "breakdown": {"category_status": status}}
check("match 우선", *(lambda r: ([x["restaurant_id"] for x in r[0]], r[1]))(
    rag._select_by_category([c(1,"match"), c(2,"mismatch"), c(3,"no_data")], "중국 요리")) and
    (([x["restaurant_id"] for x in rag._select_by_category([c(1,"match"), c(2,"mismatch"), c(3,"no_data")], "중국 요리")[0]],
      rag._select_by_category([c(1,"match"), c(2,"mismatch"), c(3,"no_data")], "중국 요리")[1]), ([1], False)))
sel, no_match = rag._select_by_category([c(2,"mismatch"), c(3,"no_data")], "중국 요리")
check("match 없으면 no_data 폴백", ([x["restaurant_id"] for x in sel], no_match), ([3], False))
sel, no_match = rag._select_by_category([c(2,"mismatch")], "중국 요리")
check("전부 mismatch → 빈 결과 + no_match=True", ([x["restaurant_id"] for x in sel], no_match), ([], True))
sel, no_match = rag._select_by_category([c(1,"n/a"), c(2,"n/a")], None)
check("카테고리 없으면 전량 유지", ([x["restaurant_id"] for x in sel], no_match), ([1,2], False))

print("\n" + "="*60)
print(f"결과: {'모두 통과' if not FAIL else f'{len(FAIL)}건 실패 -> {FAIL}'}")
sys.exit(1 if FAIL else 0)
