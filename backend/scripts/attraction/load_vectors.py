"""생성된 관광지·행사 Document를 pgvector에 append."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.data_pipeline.attraction.models import RAGDocument
from vector_db.attraction.loader import load_documents


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2] / "data" / "attraction" / "documents"
    documents = []
    for path in (root / "attractions.jsonl", root / "events.jsonl"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            documents.append(RAGDocument(**json.loads(line)))
    print(json.dumps(load_documents(documents, batch_size=args.batch_size), ensure_ascii=False))


if __name__ == "__main__":
    main()
