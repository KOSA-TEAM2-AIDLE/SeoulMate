"""Export pending augmentation cases into a compact Markdown review queue."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).parents[2] / "data" / "attraction" / "DSPy" / "augmentation_draft"
    source = root / "augmentation_draft.jsonl"
    target = root / "REVIEW_QUEUE.md"
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    output = [
        "# Attraction train/dev augmentation review queue",
        "",
        "각 사례는 SeoulMate DB의 관광 장소 설명·연결 리뷰 원문과 대조한 상태입니다. `reviewed` 사례만 이후 train/dev 반영 후보가 됩니다.",
        "",
    ]
    for row in rows:
        metadata = row["metadata"]
        output.extend([
            f"## {row['example_id']} — {metadata['scenario_type']} → {metadata['target_split']}",
            "",
            f"- Question: {row['input']['question']}",
            f"- Expected IDs: {', '.join(row['expected']['selected_place_ids']) or '(none)'}",
            "- Candidates:",
        ])
        for candidate in row["input"]["candidates"]:
            constraints = " (excluded)" if candidate.get("constraints") else ""
            output.append(f"  - `{candidate['place_id']}` {candidate['name']}{constraints} — {(candidate.get('description') or '')[:180]}")
        output.extend([
            f"- Review decision: `{row['review_status']}`",
            f"- Review note: {row.get('review_notes') or '(none)'}",
            "",
        ])
    target.write_text("\n".join(output), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
