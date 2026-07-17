"""원본 Visit Seoul CSV에서 정제 CSV와 RAG Document JSONL을 생성한다."""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from scripts.data_pipeline.attraction.documents import build_documents
from scripts.data_pipeline.attraction.loader import read_visit_seoul_csv
from scripts.data_pipeline.attraction.transform import classify_and_filter_rows


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "attraction"


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, documents) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as target:
        for document in documents:
            target.write(json.dumps(asdict(document), ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rows = []
    for path in sorted((DATA_DIR / "raw").glob("visit_seoul_master_*_no_food_accommodation.csv")):
        rows.extend(read_visit_seoul_csv(path))
    result = classify_and_filter_rows(rows, as_of=args.as_of)
    documents = build_documents([*result.attractions, *result.events], generated_on=args.as_of)
    report = {"as_of": args.as_of.isoformat(), "input_rows": len(rows), "attractions": len(result.attractions), "active_events": len(result.events), "quarantine": len(result.quarantine), "documents": len(documents)}
    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    _write_csv(DATA_DIR / "processed" / "attractions.csv", [asdict(item) for item in result.attractions])
    _write_csv(DATA_DIR / "processed" / "events_active.csv", [asdict(item) for item in result.events])
    _write_csv(DATA_DIR / "processed" / "events_quarantine.csv", [asdict(item) for item in result.quarantine])
    _write_jsonl(DATA_DIR / "documents" / "attractions.jsonl", [doc for doc in documents if doc.metadata["kind"] == "attraction"])
    _write_jsonl(DATA_DIR / "documents" / "events.jsonl", [doc for doc in documents if doc.metadata["kind"] == "event"])
    manifest = DATA_DIR / "manifests" / "build_report.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
