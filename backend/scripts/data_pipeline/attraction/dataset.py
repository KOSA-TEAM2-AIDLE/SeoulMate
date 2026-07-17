"""관광지·행사·리뷰 CSV를 언어별 DB 적재 dataset으로 조립한다."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

from domains.attraction.taxonomy import category_metadata
from scripts.data_pipeline.attraction.loader import read_visit_seoul_csv
from scripts.data_pipeline.attraction.models import (
    AttractionCleaningReport,
    AttractionPlaceRecord,
    AttractionReviewRecord,
    CleanedAttractionDataset,
    ProcessedPlace,
)
from scripts.data_pipeline.attraction.transform import classify_and_filter_rows


SUPPORTED_LANGUAGES = ("ko", "en")


def _text(value: object) -> str:
    return str(value or "").strip()


def _rating(value: object) -> float | None:
    try:
        rating = float(_text(value))
    except ValueError:
        return None
    return rating if 0 <= rating <= 5 else None


def _read_review_rows(data_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    csv.field_size_limit(10_000_000)
    for path in sorted((data_dir / "raw" / "reviews").glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as source:
            rows.extend(
                {
                    key: _text(value)
                    for key, value in row.items()
                }
                for row in csv.DictReader(source)
            )
    if not rows:
        raise FileNotFoundError(
            f"관광 리뷰 CSV가 없습니다: {data_dir / 'raw' / 'reviews'}"
        )
    return rows


def _review_quality(row: dict[str, str]) -> tuple[int, int]:
    return (
        int(row.get("crawl_status") == "success"),
        int(bool(row.get("original_text"))),
    )


def _deduplicate_reviews(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], int]:
    selected: dict[tuple[str, str], dict[str, str]] = {}
    missing_identity = 0
    for row in rows:
        place_key = row.get("place_key", "")
        review_id = row.get("review_id", "")
        if not place_key or not review_id:
            missing_identity += 1
            continue
        key = (place_key, review_id)
        if key not in selected or _review_quality(row) > _review_quality(selected[key]):
            selected[key] = row
    return list(selected.values()), missing_identity


def _review_content(row: dict[str, str], language: str) -> str:
    if language == "ko":
        return row.get("korean_text", "") or row.get("original_text", "")
    if row.get("original_lang", "").casefold().startswith("en"):
        return row.get("original_text", "")
    return ""


def _source_language(source_cid: str) -> str | None:
    normalized = source_cid.strip().casefold()
    if normalized.startswith("kop"):
        return "ko"
    if normalized.startswith("enp"):
        return "en"
    return None


def _review_summary(
    rows: list[dict[str, str]],
) -> dict[str, dict[str, int | float | None]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("crawl_status") == "success" and row.get("original_text"):
            grouped[row["place_key"]].append(row)

    result: dict[str, dict[str, int | float | None]] = {}
    for place_key, reviews in grouped.items():
        ratings = [
            rating
            for row in reviews
            if (rating := _rating(row.get("rating"))) is not None
        ]
        result[place_key] = {
            "rating": round(sum(ratings) / len(ratings), 3) if ratings else None,
            "review_count": len(reviews),
            "english_review_count": sum(
                row.get("original_lang", "").casefold().startswith("en")
                for row in reviews
            ),
            "foreign_review_count": sum(
                row.get("original_lang", "").casefold() not in {"", "ko"}
                for row in reviews
            ),
        }
    return result


def _place_record(
    place: ProcessedPlace,
    summary: dict[str, int | float | None],
) -> AttractionPlaceRecord:
    category = category_metadata(place.category, place.kind)
    return AttractionPlaceRecord(
        id=place.place_key,
        source_cid=place.source_cid,
        language=place.lang,
        kind=place.kind,
        name=place.name,
        category=place.category,
        category_primary=str(category.get("category_primary") or ""),
        category_secondary=str(category.get("category_secondary") or ""),
        summary=place.summary,
        description=place.description or place.summary,
        tags=place.tags,
        address=place.road_address,
        latitude=place.latitude,
        longitude=place.longitude,
        hours=place.hours,
        fee=place.fee,
        image=place.image_url or None,
        link=place.homepage_url or None,
        start_date=place.start_date,
        end_date=place.end_date,
        rating=(
            float(summary["rating"])
            if summary.get("rating") is not None
            else None
        ),
        review_count=int(summary.get("review_count") or 0),
        english_review_count=int(summary.get("english_review_count") or 0),
        foreign_review_count=int(summary.get("foreign_review_count") or 0),
    )


def clean_attraction_datasets(
    data_dir: Path,
    as_of: date,
) -> tuple[CleanedAttractionDataset, ...]:
    """원천을 한·영 적재 dataset으로 정제한다.

    DB나 외부 API를 호출하지 않으므로 dry-run에서 그대로 사용할 수 있다.
    """
    source_paths = sorted(
        (data_dir / "raw").glob(
            "visit_seoul_master_*_no_food_accommodation.csv"
        )
    )
    if not source_paths:
        raise FileNotFoundError(f"관광지 원천 CSV가 없습니다: {data_dir / 'raw'}")

    source_rows = [
        row
        for path in source_paths
        for row in read_visit_seoul_csv(path)
    ]
    filtered = classify_and_filter_rows(source_rows, as_of=as_of)
    active_places = [*filtered.attractions, *filtered.events]

    raw_reviews = _read_review_rows(data_dir)
    deduplicated_reviews, missing_review_identity = _deduplicate_reviews(raw_reviews)
    valid_review_rows = [
        row
        for row in deduplicated_reviews
        if row.get("crawl_status") == "success" and row.get("original_text")
    ]
    summaries = _review_summary(valid_review_rows)

    source_places_by_language = {
        language: sum(
            _text(row.get("lang_code_id")).casefold() == language
            for row in source_rows
        )
        for language in SUPPORTED_LANGUAGES
    }
    datasets: list[CleanedAttractionDataset] = []
    for language in SUPPORTED_LANGUAGES:
        language_places = [
            place for place in active_places if place.lang == language
        ]
        active_ids = {place.place_key for place in language_places}
        reviews: list[AttractionReviewRecord] = []
        empty_reviews = 0
        orphan_reviews = missing_review_identity
        for row in deduplicated_reviews:
            place_key = row.get("place_key", "")
            if place_key not in active_ids:
                orphan_reviews += 1
                continue
            content = _review_content(row, language)
            if row.get("crawl_status") != "success" or not content:
                empty_reviews += 1
                continue
            reviews.append(
                AttractionReviewRecord(
                    source_review_id=row["review_id"],
                    attraction_id=place_key,
                    language=language,
                    rating=_rating(row.get("rating")),
                    content=content,
                )
            )

        places = tuple(
            _place_record(place, summaries.get(place.place_key, {}))
            for place in language_places
        )
        report = AttractionCleaningReport(
            language=language,
            source_places=source_places_by_language[language],
            cleaned_places=len(places),
            attractions=sum(place.kind == "attraction" for place in places),
            active_events=sum(place.kind == "event" for place in places),
            expired_events=sum(
                row.reason == "expired_event"
                and _source_language(row.source_cid) == language
                for row in filtered.quarantine
            ),
            invalid_event_dates=sum(
                row.reason == "invalid_event_end_date"
                and _source_language(row.source_cid) == language
                for row in filtered.quarantine
            ),
            source_reviews=len(raw_reviews),
            cleaned_reviews=len(reviews),
            orphan_reviews=orphan_reviews,
            empty_reviews=empty_reviews,
        )
        datasets.append(
            CleanedAttractionDataset(
                language=language,
                places=places,
                reviews=tuple(reviews),
                report=report,
            )
        )
    return tuple(datasets)


__all__ = ["clean_attraction_datasets"]
