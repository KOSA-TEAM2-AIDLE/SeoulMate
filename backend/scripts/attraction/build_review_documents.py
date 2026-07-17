"""Google Maps 원시 리뷰를 활성 관광지·행사에 연결해 Document로 만든다."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from scripts.data_pipeline.attraction.reviews import build_review_documents, process_review_rows


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "attraction"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main() -> None:
    raw_paths = sorted((DATA / "raw" / "reviews").glob("*.csv"))
    if not raw_paths:
        raise FileNotFoundError("data/attraction/raw/reviews에 원시 리뷰 CSV가 없습니다.")
    active_keys = {row["place_key"] for file in (DATA / "processed" / "attractions.csv", DATA / "processed" / "events_active.csv") if file.exists() for row in _read_csv(file)}
    rows = [row for path in raw_paths for row in _read_csv(path)]
    result = process_review_rows(rows, active_place_keys=active_keys)
    documents = build_review_documents(result.reviews, generated_on=date.today().isoformat())
    _write_csv(DATA / "processed" / "reviews.csv", result.reviews)
    _write_csv(DATA / "processed" / "review_summary.csv", result.summary)
    output = DATA / "documents" / "reviews.jsonl"; output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(asdict(document), ensure_ascii=False) + "\n" for document in documents), encoding="utf-8")
    report = {"raw_rows": len(rows), "active_places": len(active_keys), "clean_reviews": len(result.reviews), "review_documents": len(documents), "excluded_rows": result.excluded_count}
    (DATA / "manifests" / "review_build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
