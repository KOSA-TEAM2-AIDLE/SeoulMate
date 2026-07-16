"""기존 노트북 스냅샷을 현재 선택 계약의 provisional JSONL로 변환한다."""

from __future__ import annotations

import argparse
import json
from itertools import cycle, islice
from pathlib import Path

import psycopg2

from core.config import DB_CONFIG


SPLIT_COUNTS = {"train": 30, "dev": 10, "test": 10, "blind": 20}
DEFAULT_LEGACY_DIR = Path(
    "/Users/younder/Desktop/아이티센 AIE 부트캠프/999.프로젝트/"
    "2.2차미니프로젝트/999.datacheck/data/evaluation/dspy_prompt_optimization"
)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _db_fillers() -> list[dict]:
    with psycopg2.connect(**DB_CONFIG) as connection:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT content, metadata
                FROM attraction_vector_documents
                WHERE metadata->>'kind'='attraction' AND metadata->>'lang'='ko'
                ORDER BY document_id LIMIT 100
            """)
            rows = cursor.fetchall()
    fillers = []
    for content, metadata in rows:
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        values = {}
        for line in content.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                values[key] = value
        fillers.append({
            "place_id": str(metadata["place_key"]),
            "name": values.get("Name") or str(metadata["place_key"]),
            "category": str(metadata.get("category") or values.get("Category") or "관광지"),
            "description": values.get("Description") or values.get("Summary"),
            "reviews": [],
        })
    if len(fillers) < 5:
        raise RuntimeError("Vector DB에 provisional 후보가 부족합니다.")
    return fillers


def _legacy_candidate(candidate: dict, rank: int) -> dict:
    reviews = [
        str(review.get("text") or "").strip()
        for review in candidate.get("matched_reviews", [])
        if str(review.get("text") or "").strip()
    ][:5]
    congestion = None
    if candidate.get("congestion_available"):
        parts = [
            f"level={candidate.get('congestion_level')}" if candidate.get("congestion_level") else None,
            f"basis={candidate.get('congestion_basis_region')}" if candidate.get("congestion_basis_region") else None,
            f"observed_at={candidate.get('congestion_observed_at')}" if candidate.get("congestion_observed_at") else None,
        ]
        congestion = "; ".join(part for part in parts if part) or None
    description = candidate.get("description") or candidate.get("profile_text") or candidate.get("document_text")
    distance = candidate.get("distance_km")
    return {
        "place_id": str(candidate.get("cid_base") or candidate.get("place_id") or f"legacy-{rank}"),
        "rank": rank,
        "name": str(candidate.get("display_title") or candidate.get("name") or f"후보 {rank}"),
        "category": str(candidate.get("category2") or candidate.get("category1") or "관광지"),
        "distance_m": round(float(distance) * 1000, 1) if distance is not None else None,
        "description": str(description).strip() if description else None,
        "reviews": reviews,
        "event_start_date": None,
        "event_end_date": None,
        "congestion": congestion,
    }


def _case(record: dict, *, case_id: str, label: dict | None, fillers: list[dict]) -> dict:
    evidence = record.get("evidence") or {}
    legacy = [_legacy_candidate(value, index) for index, value in enumerate(evidence.get("candidates") or [], 1)]
    used = {candidate["place_id"] for candidate in legacy}
    for filler in fillers:
        if len(legacy) >= 5:
            break
        if filler["place_id"] in used:
            continue
        legacy.append({**filler, "rank": len(legacy) + 1, "distance_m": None, "event_start_date": None, "event_end_date": None, "congestion": None})
        used.add(filler["place_id"])
    acceptable = [candidate["place_id"] for candidate in legacy[:3]]
    expected = (label or {}).get("expected") or {}
    conditions = [str(value) for value in expected.get("intents", []) if str(value).strip()]
    forbidden = list((label or {}).get("must_not") or [])
    if not forbidden:
        forbidden = list(((record.get("private_criteria") or {}).get("must_not") or []))
    return {
        "case_id": case_id,
        "source": {
            "type": "provisional_notebook_snapshot",
            "reference": "Tourism_Agent_DSPy_Prompt_Optimization.ipynb",
            "source_case_id": str(record.get("case_id")),
        },
        "public_input": {
            "question": str(record["question"]),
            "language": str(record.get("language") or "ko"),
            "location": ((evidence.get("center") or {}).get("name")),
            "themes": conditions,
            "selection_count": 3,
            "candidates": legacy[:10],
        },
        "private_label": {
            "acceptable_place_ids": acceptable,
            "required_conditions": conditions,
            "forbidden_claims": [str(value) for value in forbidden],
            "reference_answer": (label or {}).get("reference_answer"),
            "human_review_status": "provisional",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-dir", type=Path, default=DEFAULT_LEGACY_DIR)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "data")
    args = parser.parse_args(argv)
    recommendation_rows = []
    labels = {}
    for split in ("train", "dev", "test"):
        public_rows = _read_jsonl(args.legacy_dir / f"{split}_model_inputs.jsonl")
        private_rows = _read_jsonl(args.legacy_dir / f"{split}_private_labels.jsonl")
        labels.update({row["case_id"]: row for row in private_rows})
        recommendation_rows.extend(row for row in public_rows if (row.get("evidence") or {}).get("candidates"))
    blind_rows = _read_jsonl(args.legacy_dir / "blind_challenge_dataset.jsonl")
    if len(recommendation_rows) < 18 or len(blind_rows) < 20:
        raise RuntimeError("기존 provisional 소스가 부족합니다.")
    source_groups = {
        "train": recommendation_rows[:10],
        "dev": recommendation_rows[10:14],
        "test": recommendation_rows[14:18],
        "blind": blind_rows[:20],
    }
    fillers = _db_fillers()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for split, count in SPLIT_COUNTS.items():
        sources = list(islice(cycle(source_groups[split]), count))
        rows = [
            _case(source, case_id=f"{split}_{index:03d}", label=labels.get(source.get("case_id")), fillers=fillers[index:] + fillers[:index])
            for index, source in enumerate(sources, 1)
        ]
        (args.output_dir / f"{split}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        print(f"{split}={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
