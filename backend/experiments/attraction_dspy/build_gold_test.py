"""Build a leakage-free, challenge-oriented attraction gold evaluation set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[2] / "data" / "attraction" / "DSPy"


def _rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _used_ids() -> set[str]:
    ids = set()
    for kind in ("selection", "answer", "exception"):
        for split in ("train", "dev", "test"):
            for row in _rows(ROOT / kind / f"{split}.jsonl"):
                ids.update(item["place_id"] for item in row["input"].get("candidates", []))
                ids.update(row.get("metadata", {}).get("source_place_cids", []))
    return ids


def build_gold_test() -> list[dict]:
    used = _used_ids()
    pool_by_id = {}
    for row in _rows(ROOT / "normalized" / "place_review_summary.jsonl"):
        if row["cid"] not in used and row["candidate"].get("description"):
            pool_by_id.setdefault(row["cid"], row)
    pool = list(pool_by_id.values())
    if len(pool) < 120:
        raise ValueError("독립 gold 후보 풀이 충분하지 않습니다.")
    result = []
    for index in range(40):
        chunk = pool[index * 3:(index + 1) * 3]
        language = "ko" if index % 2 == 0 else "en"
        candidates = []
        for rank, raw in enumerate(chunk, start=1):
            candidate = dict(raw["candidate"])
            candidate["rank"] = rank
            candidate["constraints"] = []
            candidates.append(candidate)
        kind = "multi_candidate" if index < 15 else "excluded_constraint" if index < 25 else "context_grounded" if index < 35 else "no_result"
        selected = [candidates[0]["place_id"]]
        if kind == "excluded_constraint":
            candidates[1]["constraints"] = [{"source_text": "제외 조건", "normalized_text": "제외", "kind": "excluded", "status": "conflict", "evidence": ["gold constraint"]}]
        elif kind == "context_grounded":
            candidates[0]["congestion"] = {"status": "available", "value": "보통", "basis": "gold synthetic context", "observed_at": "2026-07-18T10:00:00+09:00"}
            candidates[0]["weather"] = {"status": "available", "value": "맑음", "basis": "gold synthetic context", "observed_at": "2026-07-18T10:00:00+09:00"}
        elif kind == "no_result":
            selected = []
            for candidate in candidates:
                candidate["constraints"] = [{"source_text": "제외 조건", "normalized_text": "제외", "kind": "excluded", "status": "conflict", "evidence": ["gold constraint"]}]
        group = hashlib.sha256(f"gold-v2-{index}".encode()).hexdigest()[:16]
        reasons = {place_id: "gold source-grounded candidate" for place_id in selected}
        result.append({
            "example_id": f"gold-v2-{index + 1:03d}",
            "input": {"question": "조건에 맞는 관광지를 추천해줘" if language == "ko" else "Recommend attractions that match the conditions.", "language": language, "location": None, "themes": [], "candidates": candidates},
            "expected": {"selected_place_ids": selected, "forbidden_place_ids": [], "selection_reasons": reasons, "max_recommendations": 3, "allow_fewer_results": True},
            "metadata": {"scenario_type": kind, "split_group": group, "synthetic_context": kind == "context_grounded", "source_document_ids": [doc for raw in chunk for doc in raw["source_document_ids"]], "source_review_ids": [review for raw in chunk for review in raw["source_review_ids"]], "source_place_cids": [raw["cid"] for raw in chunk], "split": "gold_test"},
            "review_status": "pending", "review_notes": "Generated from unused normalized candidates; review before benchmark publication.",
        })
    return result


def main() -> int:
    rows = build_gold_test()
    target = ROOT / "gold_test" / "gold_test.jsonl"
    target.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
