"""Build a review-only, leakage-free draft for future train/dev augmentation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[2] / "data" / "attraction" / "DSPy"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _reserved(dataset_root: Path) -> tuple[set[str], set[str]]:
    place_ids: set[str] = set()
    groups: set[str] = set()
    for kind in ("selection", "answer", "exception"):
        for split in ("train", "dev", "test"):
            for row in _rows(dataset_root / kind / f"{split}.jsonl"):
                place_ids.update(item["place_id"] for item in row["input"].get("candidates", []))
                place_ids.update(row.get("metadata", {}).get("source_place_cids", []))
                groups.add(row.get("metadata", {}).get("split_group", ""))
    for row in _rows(dataset_root / "gold_test" / "gold_test.jsonl"):
        place_ids.update(item["place_id"] for item in row["input"].get("candidates", []))
        place_ids.update(row.get("metadata", {}).get("source_place_cids", []))
        groups.add(row.get("metadata", {}).get("split_group", ""))
    return place_ids, groups


def build_augmentation_draft(dataset_root: Path = ROOT) -> list[dict]:
    """Create 32 pending cases; never use existing train/dev/test or gold sources."""

    reserved_ids, reserved_groups = _reserved(dataset_root)
    pool_by_id: dict[str, dict] = {}
    for raw in _rows(dataset_root / "normalized" / "place_review_summary.jsonl"):
        cid = raw["cid"]
        if cid not in reserved_ids and raw["candidate"].get("description"):
            pool_by_id.setdefault(cid, raw)
    pool = list(pool_by_id.values())
    if len(pool) < 96:
        raise ValueError("보강 초안에 필요한 독립 후보 풀이 부족합니다.")

    rows: list[dict] = []
    kinds = ["multi_candidate"] * 12 + ["excluded_constraint"] * 8 + ["context_grounded"] * 8 + ["no_result"] * 4
    for index, kind in enumerate(kinds):
        chunk = pool[index * 3:(index + 1) * 3]
        group = hashlib.sha256(f"augmentation-v1-{index}".encode()).hexdigest()[:16]
        if group in reserved_groups:
            raise ValueError("보강 초안 split_group이 기존 데이터와 충돌합니다.")
        language = "ko" if index % 2 == 0 else "en"
        candidates = []
        for rank, raw in enumerate(chunk, start=1):
            candidate = dict(raw["candidate"])
            candidate["rank"] = rank
            candidate["constraints"] = []
            candidates.append(candidate)
        selected = [candidates[0]["place_id"]]
        if kind == "excluded_constraint":
            candidates[1]["constraints"] = [{
                "source_text": "제외 조건", "normalized_text": "제외", "kind": "excluded",
                "status": "conflict", "evidence": ["augmentation constraint"],
            }]
        elif kind == "context_grounded":
            candidates[0]["congestion"] = {
                "status": "available", "value": "보통", "basis": "augmentation synthetic context",
                "observed_at": "2026-07-18T10:00:00+09:00",
            }
            candidates[0]["weather"] = {
                "status": "available", "value": "맑음", "basis": "augmentation synthetic context",
                "observed_at": "2026-07-18T10:00:00+09:00",
            }
        elif kind == "no_result":
            selected = []
            for candidate in candidates:
                candidate["constraints"] = [{
                    "source_text": "제외 조건", "normalized_text": "제외", "kind": "excluded",
                    "status": "conflict", "evidence": ["augmentation constraint"],
                }]
        target_split = "dev" if index in {4, 9, 14, 19, 25, 30} else "train"
        rows.append({
            "example_id": f"augmentation-v1-{index + 1:03d}",
            "input": {
                "question": "조건에 맞는 관광지를 추천해줘" if language == "ko" else "Recommend attractions that match the conditions.",
                "language": language, "location": None, "themes": [], "candidates": candidates,
            },
            "expected": {
                "selected_place_ids": selected, "forbidden_place_ids": [],
                "selection_reasons": {place_id: "source-grounded candidate" for place_id in selected},
                "max_recommendations": 3, "allow_fewer_results": True,
            },
            "metadata": {
                "scenario_type": kind, "split_group": group, "target_split": target_split,
                "synthetic_context": kind == "context_grounded",
                "source_document_ids": [doc for raw in chunk for doc in raw["source_document_ids"]],
                "source_review_ids": [review for raw in chunk for review in raw["source_review_ids"]],
                "source_place_cids": [raw["cid"] for raw in chunk],
                "split": "augmentation_draft",
            },
            "review_status": "pending",
            "review_notes": "Draft is isolated from gold and existing splits; human review required before train/dev use.",
        })
    return rows


def main() -> int:
    rows = build_augmentation_draft()
    target = ROOT / "augmentation_draft" / "augmentation_draft.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
