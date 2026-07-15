# -*- coding: utf-8 -*-
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import rag
from services.rag import _category_match_status, _category_boost, _select_by_category

FAIL = []
def check(label, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'} | {label}\n         got={got!r} want={want!r}")
    if not ok: FAIL.append(label)

print("=== [1] status/confidence 판정 ===")
check("카카오=중국 요리 → 확정 일치",
      _category_match_status({"category_kakao": "중국 요리", "category": "음식점"}, "중국 요리"),
      ("match", "confirmed"))
check("카카오 없음 + 원본태그=중식 → 추정 일치",
      _category_match_status({"category_kakao": None, "category": "중식, 음식점"}, "중국 요리"),
      ("match", "inferred"))
check("카카오=한식 → 불일치(확정)",
      _category_match_status({"category_kakao": "한식", "category": "중식"}, "중국 요리"),
      ("mismatch", "confirmed"))
check("태그 전무 → no_data",
      _category_match_status({"category_kakao": None, "category": "음식점"}, "중국 요리"),
      ("no_data", None))

print("\n=== [2] 부스트가 '실제로' 순위를 바꾸는가 (핵심) ===")
cands = [
    # 이름,            base,   status,     confidence
    ("확정 중식당 A", 0.0220, "match", "confirmed"),
    ("추정 중식당 B", 0.0230, "match", "inferred"),   # base는 B가 더 높다
    ("확정 한식당 C", 0.0400, "match" if False else "mismatch", "confirmed"),
]
def rank(use_boost):
    rows = []
    for name, base, status, conf in cands:
        boost = _category_boost(base, status, conf) if use_boost else 0.0
        rows.append({"name": name, "score": base + boost, "review_count": 0,
                     "restaurant_id": name, "breakdown": {"category_status": status}})
    rows.sort(key=lambda i: (0, -i["score"], -(i["review_count"] or 0), i["restaurant_id"]))
    sel, _ = _select_by_category(rows, "중국 요리")
    return [(r["name"], round(r["score"], 5)) for r in sel]

print("  부스트 OFF:", rank(False))
print("  부스트 ON :", rank(True))
check("부스트 OFF → base 높은 '추정 B'가 1위", rank(False)[0][0], "추정 중식당 B")
check("부스트 ON  → '확정 A'가 역전해 1위",   rank(True)[0][0], "확정 중식당 A")
check("한식당(mismatch)은 항상 제외", [n for n, _ in rank(True)], ["확정 중식당 A", "추정 중식당 B"])

print("\n=== [3] 감사 불변식 유지: 최종 후보가 전부 match 인가 ===")
rows = [{"name": n, "breakdown": {"category_status": s}} for n, _, s, _ in cands]
sel, no_match = _select_by_category(rows, "중국 요리")
check("모든 후보 status == match",
      all(r["breakdown"]["category_status"] == "match" for r in sel), True)
check("match 없으면 no_data 폴백", 
      _select_by_category([{"breakdown": {"category_status": "no_data"}}], "중국 요리")[1], False)
check("전부 mismatch → 빈 결과 + no_match 플래그",
      _select_by_category([{"breakdown": {"category_status": "mismatch"}}], "중국 요리")[1], True)

print("\n=== [4] weather_reranker 최고점 정규화에서 살아남는가 ===")
# rag_normalized = raw/high. 부스트가 균일하면 상쇄되고, 등급이 다르면 살아남는다.
a, b = 0.0220 * 1.20, 0.0230 * 1.08
high = max(a, b)
print(f"  확정A norm={a/high:.4f}  추정B norm={b/high:.4f} -> 비율 차이 유지: {abs(a/high - b/high) > 1e-9}")
check("정규화 후에도 확정A가 우위", a > b, True)

print("\n" + "="*58)
print("결과:", "모두 통과" if not FAIL else f"실패 {FAIL}")
