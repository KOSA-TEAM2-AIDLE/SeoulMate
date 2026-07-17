from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MENU_SOURCE = ROOT / "restaurant_menu_L3.csv"
DEFAULT_TRANSLATION_CACHE = ROOT / "translation_cache.json"
OUTPUT_COLUMNS = {
    "restaurant": [
        "id", "name", "phone", "address", "postal_code", "lat", "lng",
        "category", "hours", "description", "image", "link", "review_count",
        "rating", "category_kakao", "description_kakao", "last_order",
        "kakao_place_id", "kakao_place_url", "menu_price_min",
        "menu_price_median", "menu_count", "has_parking",
        "has_group_seating", "has_private_room", "has_baby_chair",
        "has_kids_menu", "allows_pets", "has_disabled_access", "hours_source",
    ],
    "review": ["id", "restaurant_id", "rating", "content"],
    "menu": [
        "id", "restaurant_id", "menu_order", "menu_name", "price_text",
        "price_value", "is_main",
    ],
}
INTEGER_COLUMNS = {
    "id", "restaurant_id", "review_count", "menu_price_min",
    "menu_price_median", "menu_count", "menu_order", "price_value",
}
BOOLEAN_COLUMNS = {
    "has_parking", "has_group_seating", "has_private_room", "has_baby_chair",
    "has_kids_menu", "allows_pets", "has_disabled_access", "is_main",
}
ENGLISH_NAME_FIXES = {
    "5035631": "Tani Next Door",
    "17623480": "Bar 420",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def clean_value(column: str, value: str | None) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if column in INTEGER_COLUMNS:
        return str(int(float(value)))
    if column in BOOLEAN_COLUMNS:
        lowered = value.lower()
        if lowered in {"true", "1", "yes"}:
            return "true"
        if lowered in {"false", "0", "no"}:
            return "false"
        raise ValueError(f"Invalid boolean for {column}: {value!r}")
    return value


def clean_row(row: dict[str, str], columns: list[str]) -> dict[str, str]:
    return {column: clean_value(column, row.get(column)) for column in columns}


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def duplicate_count(rows: list[dict[str, str]], columns: tuple[str, ...]) -> int:
    counts = Counter(tuple(row[column] for column in columns) for row in rows)
    return sum(count - 1 for count in counts.values() if count > 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare SeoulMate CSVs for DB import")
    parser.add_argument("--menu-source", type=Path, default=DEFAULT_MENU_SOURCE)
    parser.add_argument("--translation-cache", type=Path, default=DEFAULT_TRANSLATION_CACHE)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "import_ready")
    args = parser.parse_args()

    restaurant_ko = read_csv(ROOT / "restaurant_L3.csv")
    restaurant_en = read_csv(ROOT / "restaurant_L3_en.csv")
    review_ko = read_csv(ROOT / "restaurant_review_L2.csv")
    review_en = read_csv(ROOT / "restaurant_review_L2_en.csv")
    menu_source = read_csv(args.menu_source)
    with args.translation_cache.open("r", encoding="utf-8") as handle:
        translation_cache: dict[str, str] = json.load(handle)

    for row in menu_source:
        if not row["menu_name_en"].strip():
            row["menu_name_en"] = translation_cache.get(row["menu_name_ko"], "").strip()

    unresolved_translations = sum(not row["menu_name_en"].strip() for row in menu_source)
    if unresolved_translations:
        raise ValueError(f"Unresolved English menu translations: {unresolved_translations}")

    for row in restaurant_en:
        if row["id"] in ENGLISH_NAME_FIXES and not row["name"].strip():
            row["name"] = ENGLISH_NAME_FIXES[row["id"]]

    restaurant_ko_clean = [clean_row(row, OUTPUT_COLUMNS["restaurant"]) for row in restaurant_ko]
    restaurant_en_clean = [clean_row(row, OUTPUT_COLUMNS["restaurant"]) for row in restaurant_en]
    review_ko_clean = [clean_row(row, OUTPUT_COLUMNS["review"]) for row in review_ko]
    review_en_clean = [clean_row(row, OUTPUT_COLUMNS["review"]) for row in review_en]

    restaurant_ko_ids = {row["id"] for row in restaurant_ko_clean}
    restaurant_en_ids = {row["id"] for row in restaurant_en_clean}
    menu_ko: list[dict[str, str]] = []
    menu_en_all: list[dict[str, str]] = []
    menu_en: list[dict[str, str]] = []
    menu_en_rejected: list[dict[str, str]] = []

    for source in menu_source:
        common = {
            "id": source["id"],
            "restaurant_id": source["restaurant_id"],
            "menu_order": source["menu_order"],
            "price_text": source["price_text"],
            "price_value": source["price_value"],
            "is_main": source["is_main"],
        }
        ko_row = clean_row(
            {**common, "menu_name": source["menu_name_ko"]}, OUTPUT_COLUMNS["menu"]
        )
        if ko_row["restaurant_id"] not in restaurant_ko_ids:
            raise ValueError(f"Korean menu {ko_row['id']} has no restaurant FK")
        menu_ko.append(ko_row)

        en_row = clean_row(
            {**common, "menu_name": source["menu_name_en"]}, OUTPUT_COLUMNS["menu"]
        )
        menu_en_all.append(en_row)

        reasons: list[str] = []
        if source["restaurant_id"] not in restaurant_en_ids:
            reasons.append("missing_restaurant_en")
        if reasons:
            menu_en_rejected.append({**source, "rejection_reason": ";".join(reasons)})
            continue
        menu_en.append(en_row)

    output = args.output
    write_csv(output / "restaurant_ko.csv", restaurant_ko_clean, OUTPUT_COLUMNS["restaurant"])
    write_csv(output / "restaurant_en.csv", restaurant_en_clean, OUTPUT_COLUMNS["restaurant"])
    write_csv(output / "restaurant_review_ko.csv", review_ko_clean, OUTPUT_COLUMNS["review"])
    write_csv(output / "restaurant_review_en.csv", review_en_clean, OUTPUT_COLUMNS["review"])
    write_csv(output / "restaurant_menu_ko.csv", menu_ko, OUTPUT_COLUMNS["menu"])
    write_csv(output / "restaurant_menu_en_all.csv", menu_en_all, OUTPUT_COLUMNS["menu"])
    write_csv(output / "restaurant_menu_en.csv", menu_en, OUTPUT_COLUMNS["menu"])
    write_csv(
        output / "restaurant_menu_en_rejected.csv",
        menu_en_rejected,
        list(menu_source[0]) + ["rejection_reason"],
    )

    report = {
        "restaurant_ko": len(restaurant_ko_clean),
        "restaurant_en": len(restaurant_en_clean),
        "restaurant_review_ko": len(review_ko_clean),
        "restaurant_review_en": len(review_en_clean),
        "restaurant_menu_ko": len(menu_ko),
        "restaurant_menu_en_all_translated": len(menu_en_all),
        "restaurant_menu_en": len(menu_en),
        "restaurant_menu_en_rejected": len(menu_en_rejected),
        "rejection_reasons": dict(Counter(
            reason
            for row in menu_en_rejected
            for reason in row["rejection_reason"].split(";")
        )),
        "checks": {
            "restaurant_ko_duplicate_id": duplicate_count(restaurant_ko_clean, ("id",)),
            "restaurant_en_duplicate_id": duplicate_count(restaurant_en_clean, ("id",)),
            "menu_ko_duplicate_id": duplicate_count(menu_ko, ("id",)),
            "menu_en_duplicate_id": duplicate_count(menu_en, ("id",)),
            "menu_en_unresolved_translation": sum(not row["menu_name"] for row in menu_en_all),
            "review_ko_duplicate_id": duplicate_count(review_ko_clean, ("id",)),
            "review_en_duplicate_id": duplicate_count(review_en_clean, ("id",)),
            "menu_ko_invalid_fk": sum(row["restaurant_id"] not in restaurant_ko_ids for row in menu_ko),
            "menu_en_invalid_fk": sum(row["restaurant_id"] not in restaurant_en_ids for row in menu_en),
            "restaurant_en_missing_name": sum(not row["name"] for row in restaurant_en_clean),
        },
    }
    with (output / "validation_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
