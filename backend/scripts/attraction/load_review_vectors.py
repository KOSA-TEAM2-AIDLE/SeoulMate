"""정제된 관광지 리뷰 Document를 기존 attraction pgvector 저장소에 적재한다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.data_pipeline.attraction.models import RAGDocument
from vector_db.attraction.loader import load_documents


def read_review_documents(path: Path) -> list[RAGDocument]:
    if not path.exists():
        raise FileNotFoundError(f"리뷰 Document 파일이 없습니다: {path}")
    return [RAGDocument(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[2] / "data" / "attraction" / "documents" / "reviews.jsonl"
    result = load_documents(read_review_documents(path), batch_size=args.batch_size)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
