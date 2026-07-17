import csv
from pathlib import Path


REQUIRED_COLUMNS = {"cid", "lang_code_id", "category_path", "name", "description_text"}


def read_visit_seoul_csv(path: Path) -> list[dict[str, str]]:
    # Visit Seoul 원본은 사용하지 않는 description_html에도 128KiB를 넘는 HTML이 있다.
    csv.field_size_limit(10_000_000)
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}에 필수 컬럼이 없습니다: {sorted(missing)}")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]
