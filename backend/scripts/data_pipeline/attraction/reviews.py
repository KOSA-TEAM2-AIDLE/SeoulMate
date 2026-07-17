from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
from typing import Iterable

from scripts.data_pipeline.attraction.models import RAGDocument


@dataclass(frozen=True)
class ReviewProcessResult:
    reviews: list[dict]
    summary: list[dict]
    excluded_count: int


def _text(value: object) -> str:
    return str(value or "").strip()


def _rating(value: object) -> float | None:
    try:
        return float(_text(value))
    except ValueError:
        return None


def _quality(row: dict) -> tuple[int, int]:
    return (int(_text(row.get("crawl_status")) == "success"), int(bool(_text(row.get("original_text")))))


def process_review_rows(rows: Iterable[dict[str, object]], *, active_place_keys: set[str]) -> ReviewProcessResult:
    candidates: dict[tuple[str, str], dict] = {}
    excluded_count = 0
    for source in rows:
        row = {key: _text(value) for key, value in source.items()}
        place_key, review_id = row.get("place_key", ""), row.get("review_id", "")
        if not place_key or not review_id or place_key not in active_place_keys:
            excluded_count += 1
            continue
        key = (place_key, review_id)
        if key not in candidates or _quality(row) > _quality(candidates[key]):
            candidates[key] = row
    reviews = []
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in candidates.values():
        if row.get("crawl_status") != "success" or not row.get("original_text"):
            excluded_count += 1
            continue
        row["rating"] = _rating(row.get("rating"))
        grouped[row["place_key"]].append(row)
        reviews.append(row)
    summary = []
    for place_key, values in sorted(grouped.items()):
        ratings = [row["rating"] for row in values if row["rating"] is not None]
        summary.append({
            "place_key": place_key, "review_count": len(values),
            "avg_rating": round(sum(ratings) / len(ratings), 3) if ratings else None,
            "english_text_review_count": sum(row.get("original_lang") == "en" for row in values),
            "foreign_text_review_count": sum(row.get("original_lang") not in {"", "ko"} for row in values),
        })
    return ReviewProcessResult(reviews, summary, excluded_count)


def build_review_documents(reviews: Iterable[dict], *, generated_on: str) -> list[RAGDocument]:
    documents: list[RAGDocument] = []
    for review in reviews:
        place_key, review_id = review["place_key"], review["review_id"]
        variants = []
        korean = _text(review.get("korean_text")) or _text(review.get("original_text"))
        if korean:
            variants.append(("ko", korean))
        english = _text(review.get("original_text")) if review.get("original_lang") == "en" else ""
        if english:
            variants.append(("en", english))
        for lang, content in variants:
            document_id = f"review:{place_key}:{review_id}:{lang}"
            metadata = {"place_key": place_key, "review_id": review_id, "lang": lang, "kind": "review", "rating": review.get("rating"), "generated_on": generated_on}
            documents.append(RAGDocument(document_id, content, metadata, hashlib.sha256(content.encode()).hexdigest()))
    return documents
