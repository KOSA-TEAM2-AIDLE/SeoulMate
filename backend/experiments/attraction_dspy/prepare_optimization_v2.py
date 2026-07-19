"""Prepare a reversible train/dev augmentation dataset from DB-reviewed cases."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).parents[2] / "data" / "attraction" / "DSPy"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _answer_expected(row: dict) -> dict:
    candidates = {candidate["place_id"]: candidate for candidate in row["input"]["candidates"]}
    selected = row["expected"]["selected_place_ids"]
    language = row["input"]["language"]
    recommendations = []
    for place_id in selected:
        candidate = candidates[place_id]
        recommendations.append({
            "place_id": place_id,
            "name": candidate["name"],
            "recommendation_reason": (
                "질문의 조건을 후보 설명 근거로 충족합니다."
                if language == "ko" else "It matches the question based on the supplied candidate evidence."
            ),
            "description_evidence": [candidate.get("description") or candidate["name"]],
            "review_evidence": [],
            "congestion": candidate.get("congestion") or {"status": "unavailable", "value": None},
            "weather": candidate.get("weather") or {"status": "unavailable", "value": None},
            "visitor_note": (
                "제공된 장소 정보 기준으로 방문 전 최신 운영 정보를 확인하세요."
                if language == "ko" else "Check the latest operating information before visiting."
            ),
        })
    return {
        "language": language,
        "recommendations": recommendations,
        "no_result_reason": (
            None if selected else (
                "모든 후보가 제외 조건과 충돌합니다."
                if language == "ko" else "Every candidate conflicts with the exclusion condition."
            )
        ),
    }


def prepare_optimization_v2(root: Path = ROOT) -> dict[str, int]:
    draft = [row for row in _rows(root / "augmentation_draft" / "augmentation_draft.jsonl") if row["review_status"] == "reviewed"]
    if len(draft) != 32:
        raise ValueError(f"reviewed 보강 사례는 32개여야 합니다: {len(draft)}")
    output = root / "optimization_v2"
    if output.exists():
        raise FileExistsError(f"기존 재최적화 데이터셋을 덮어쓰지 않습니다: {output}")
    counts: dict[str, int] = {}
    for kind in ("selection", "answer"):
        for split in ("train", "dev", "test"):
            rows = _rows(root / kind / f"{split}.jsonl")
            additions = [row for row in draft if row["metadata"]["target_split"] == split]
            for source in additions:
                row = json.loads(json.dumps(source, ensure_ascii=False))
                row["example_id"] = f"{kind}-{source['example_id']}"
                row["metadata"]["split"] = split
                row["metadata"]["augmentation_source"] = source["example_id"]
                if kind == "answer":
                    row["expected"]["structured_answer"] = _answer_expected(row)
                rows.append(row)
            target = output / kind / f"{split}.jsonl"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
            counts[f"{kind}_{split}"] = len(rows)
    shutil.copytree(root / "gold_test", output / "gold_test")
    return counts


def main() -> int:
    print(json.dumps(prepare_optimization_v2(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
