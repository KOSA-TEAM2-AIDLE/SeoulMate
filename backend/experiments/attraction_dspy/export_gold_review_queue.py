"""Export pending gold cases into a compact human-review Markdown queue."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).parents[2]
    source = root / "data" / "attraction" / "DSPy" / "gold_test" / "gold_test.jsonl"
    target = root / "data" / "attraction" / "DSPy" / "gold_test" / "REVIEW_QUEUE.md"
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    sections = ["# Attraction Gold Review Queue", "", "모든 사례는 `pending`입니다. 질문이 선택 후보의 근거로 충분히 구분되는지, 기대 선택 ID가 맞는지 확인한 뒤에만 `reviewed`로 변경합니다.", ""]
    for row in rows:
        sections.extend([f"## {row['example_id']} — {row['metadata']['scenario_type']}", "", f"- Question: {row['input']['question']}", f"- Expected IDs: {', '.join(row['expected']['selected_place_ids']) or '(none)'}", "- Candidates:"])
        sections.extend(f"  - `{candidate['place_id']}` {candidate['name']} — {candidate['description'][:180]}" for candidate in row["input"]["candidates"])
        sections.extend(["- Review decision: `pending`", ""])
    target.write_text("\n".join(sections), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
