"""한·영 카페 CSV를 정제하고 PostgreSQL/pgvector에 적재한다.

기본 실행:
    uv run python -m vector_db.cafe.seed_vectordb

데이터만 검증:
    uv run python -m vector_db.cafe.seed_vectordb --dry-run

테이블을 다시 만든 뒤 적재:
    uv run python -m vector_db.cafe.seed_vectordb --rebuild
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Iterable, Iterator, Literal, Sequence

from core.config import (
    DATA_DIR,
    DB_CONFIG,
    OPENAI_API_KEY,
    OPENAI_EMBED_DIM,
    OPENAI_EMBED_MODEL,
)


Language = Literal["ko", "en"]
BATCH_SIZE = 200

CAFE_COLUMNS = (
    "id",
    "name",
    "phone",
    "address",
    "postal_code",
    "lat",
    "lng",
    "category",
    "hours",
    "description",
    "image",
    "link",
)
REVIEW_COLUMNS = ("restaurant_id", "rating", "content")
DEFAULT_CAFE_DATA_DIR = DATA_DIR / "db_seed" / "cafe"


@dataclass(frozen=True)
class CafeSeedFiles:
    """카페 적재에 필요한 네 CSV 경로 묶음."""

    ko_cafe: Path
    ko_reviews: Path
    en_cafe: Path
    en_reviews: Path

    @classmethod
    def from_directory(cls, directory: Path) -> "CafeSeedFiles":
        directory = Path(directory)
        return cls(
            ko_cafe=directory / "ko_cafe.csv",
            ko_reviews=directory / "ko_cafe_reviews.csv",
            en_cafe=directory / "en_cafe.csv",
            en_reviews=directory / "en_cafe_reviews.csv",
        )

    @property
    def paths(self) -> tuple[Path, ...]:
        return self.ko_cafe, self.ko_reviews, self.en_cafe, self.en_reviews

    def validate(self) -> None:
        missing = [str(path) for path in self.paths if not path.is_file()]
        if missing:
            raise FileNotFoundError("카페 CSV 파일을 찾을 수 없습니다: " + ", ".join(missing))


@dataclass(frozen=True)
class CafeRecord:
    id: int
    name: str
    phone: str | None
    address: str
    postal_code: str | None
    lat: float
    lng: float
    category: str | None
    hours: str | None
    description: str | None
    image: str | None
    link: str | None
    rating: float | None
    review_count: int

    @property
    def embedding_content(self) -> str:
        parts = [
            self.name,
            f"Category: {self.category}" if self.category else None,
            f"Address: {self.address}",
            self.description,
        ]
        return ". ".join(part.strip() for part in parts if part and part.strip())


@dataclass(frozen=True)
class ReviewRecord:
    source_row: int
    cafe_id: int
    rating: float | None
    content: str


@dataclass(frozen=True)
class CleaningReport:
    language: Language
    source_cafes: int
    source_reviews: int
    cleaned_cafes: int
    cleaned_reviews: int
    invalid_cafes: int
    orphan_reviews: int
    empty_reviews: int
    invalid_reviews: int
    cafes_with_reviews: int
    cafes_without_reviews: int


@dataclass(frozen=True)
class CleanedCafeDataset:
    language: Language
    cafes: tuple[CafeRecord, ...]
    reviews: tuple[ReviewRecord, ...]
    report: CleaningReport


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.replace("\x00", " ").split()).strip()
    return cleaned or None


def _required_text(row: dict[str, str], column: str, row_number: int) -> str:
    value = _clean_text(row.get(column))
    if not value:
        raise ValueError(f"{row_number}행의 필수 컬럼 {column!r}이 비어 있습니다.")
    return value


def _parse_int(value: str | None, *, column: str, row_number: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{row_number}행의 {column!r}을 정수로 변환할 수 없습니다: {value!r}"
        ) from exc


def _parse_float(value: str | None, *, column: str, row_number: int) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{row_number}행의 {column!r}을 실수로 변환할 수 없습니다: {value!r}"
        ) from exc


def _optional_rating(value: str | None) -> float | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    try:
        rating = float(cleaned)
    except ValueError:
        return None
    return rating if 0 <= rating <= 5 else None


def _read_csv(path: Path) -> list[dict[str, str]]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "cp949"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def _normalize_cafe_row(row: dict[str, str], language: Language) -> dict[str, str | None]:
    if language == "ko":
        return row
    if row.get("description") is None and str(row.get("rating") or "").startswith("http"):
        return {
            "id": row.get("id"), "name": row.get("name"), "phone": row.get("link"),
            "address": row.get("review_count"), "postal_code": row.get("image"),
            "lat": row.get("cuisine"), "lng": row.get("price"),
            "category": row.get("address"), "hours": row.get("latitude"),
            "description": row.get("longitude"), "image": row.get("telephone"),
            "link": row.get("rating"), "rating": None,
        }
    return {
        **row,
        "phone": row.get("phone") or row.get("telephone"),
        "lat": row.get("lat") or row.get("latitude"),
        "lng": row.get("lng") or row.get("longitude"),
        "category": row.get("category") or row.get("cuisine"),
    }


def _normalize_review_row(row: dict[str, str], language: Language) -> dict[str, str | None]:
    if language == "en":
        return {**row, "content": row.get("content") or row.get("review_text")}
    return row


def clean_cafe_dataset(
    cafe_path: Path,
    review_path: Path,
    language: Language,
) -> CleanedCafeDataset:
    """원천 CSV를 검증하고 카페 테이블에 연결 가능한 리뷰만 남긴다."""

    raw_cafes = [_normalize_cafe_row(row, language) for row in _read_csv(cafe_path)]
    raw_reviews = [_normalize_review_row(row, language) for row in _read_csv(review_path)]

    base_cafes: dict[int, dict[str, object]] = {}
    base_ratings: dict[int, float] = {}
    invalid_cafes = 0
    for source_row, row in enumerate(raw_cafes, start=2):
        try:
            cafe_id = _parse_int(row.get("id"), column="id", row_number=source_row)
            lat = _parse_float(row.get("lat"), column="lat", row_number=source_row)
            lng = _parse_float(row.get("lng"), column="lng", row_number=source_row)
            name = _required_text(row, "name", source_row)
            address = _required_text(row, "address", source_row)
        except ValueError:
            invalid_cafes += 1
            continue
        if cafe_id in base_cafes:
            raise ValueError(f"{cafe_path.name}에 중복 카페 ID가 있습니다: {cafe_id}")
        if not -90 <= lat <= 90 or not -180 <= lng <= 180:
            invalid_cafes += 1
            continue
        base_cafes[cafe_id] = {
            "id": cafe_id,
            "name": name,
            "phone": _clean_text(row.get("phone")),
            "address": address,
            "postal_code": _clean_text(row.get("postal_code")),
            "lat": lat,
            "lng": lng,
            "category": _clean_text(row.get("category")),
            "hours": _clean_text(row.get("hours")),
            "description": _clean_text(row.get("description")),
            "image": _clean_text(row.get("image")),
            "link": _clean_text(row.get("link")),
        }
        base_rating = _optional_rating(row.get("rating"))
        if base_rating is not None:
            base_ratings[cafe_id] = base_rating

    valid_reviews: list[ReviewRecord] = []
    ratings_by_cafe: dict[int, list[float]] = {}
    orphan_reviews = 0
    empty_reviews = 0
    invalid_reviews = 0

    for source_row, row in enumerate(raw_reviews, start=2):
        try:
            cafe_id = _parse_int(
                row.get("restaurant_id"),
                column="restaurant_id",
                row_number=source_row,
            )
        except ValueError:
            invalid_reviews += 1
            continue
        if cafe_id not in base_cafes:
            orphan_reviews += 1
            continue
        content = _clean_text(row.get("content"))
        if not content:
            empty_reviews += 1
            continue
        rating = _optional_rating(row.get("rating"))
        review = ReviewRecord(
            source_row=source_row,
            cafe_id=cafe_id,
            rating=rating,
            content=content,
        )
        valid_reviews.append(review)
        if rating is not None:
            ratings_by_cafe.setdefault(cafe_id, []).append(rating)

    review_counts: dict[int, int] = {}
    for review in valid_reviews:
        review_counts[review.cafe_id] = review_counts.get(review.cafe_id, 0) + 1

    cafes = tuple(
        CafeRecord(
            **values,
            rating=(
                round(fmean(ratings_by_cafe[cafe_id]), 1)
                if ratings_by_cafe.get(cafe_id)
                else base_ratings.get(cafe_id)
            ),
            review_count=review_counts.get(cafe_id, 0),
        )
        for cafe_id, values in base_cafes.items()
    )
    cafes_with_reviews = sum(cafe.review_count > 0 for cafe in cafes)
    report = CleaningReport(
        language=language,
        source_cafes=len(raw_cafes),
        source_reviews=len(raw_reviews),
        cleaned_cafes=len(cafes),
        cleaned_reviews=len(valid_reviews),
        invalid_cafes=invalid_cafes,
        orphan_reviews=orphan_reviews,
        empty_reviews=empty_reviews,
        invalid_reviews=invalid_reviews,
        cafes_with_reviews=cafes_with_reviews,
        cafes_without_reviews=len(cafes) - cafes_with_reviews,
    )
    return CleanedCafeDataset(
        language=language,
        cafes=cafes,
        reviews=tuple(valid_reviews),
        report=report,
    )


def load_cafe_datasets(files: CafeSeedFiles) -> tuple[CleanedCafeDataset, ...]:
    """명시적으로 전달한 CSV 경로에서 한/영 카페 데이터셋을 만든다."""
    files.validate()
    return (
        clean_cafe_dataset(files.ko_cafe, files.ko_reviews, "ko"),
        clean_cafe_dataset(files.en_cafe, files.en_reviews, "en"),
    )


def load_default_datasets(
    data_dir: Path = DEFAULT_CAFE_DATA_DIR,
) -> tuple[CleanedCafeDataset, ...]:
    """기본 시드 디렉터리를 사용하는 하위 호환 래퍼."""
    return load_cafe_datasets(CafeSeedFiles.from_directory(data_dir))


def _table_names(language: Language) -> dict[str, str]:
    if language not in {"ko", "en"}:
        raise ValueError(f"지원하지 않는 언어입니다: {language}")
    return {
        "cafe": f"cafe_{language}",
        "review": f"cafe_review_{language}",
        "cafe_embedding": f"cafe_embedding_{language}",
        "review_embedding": f"cafe_review_embedding_{language}",
    }


def _batched(items: Sequence[str], size: int) -> Iterator[Sequence[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class EmbeddingClient:
    def __init__(self, batch_size: int = BATCH_SIZE) -> None:
        from openai import OpenAI

        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.batch_size = batch_size

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for batch in _batched(texts, self.batch_size):
            response = self.client.embeddings.create(
                model=OPENAI_EMBED_MODEL,
                input=list(batch),
                dimensions=OPENAI_EMBED_DIM,
            )
            vectors.extend(item.embedding for item in response.data)
        if len(vectors) != len(texts):
            raise RuntimeError("임베딩 응답 수가 요청한 텍스트 수와 일치하지 않습니다.")
        return vectors


def _create_schema(cursor, language: Language, *, rebuild: bool) -> None:
    names = _table_names(language)
    if rebuild:
        cursor.execute(
            f"""
            DROP TABLE IF EXISTS {names['review_embedding']};
            DROP TABLE IF EXISTS {names['cafe_embedding']};
            DROP TABLE IF EXISTS {names['review']};
            DROP TABLE IF EXISTS {names['cafe']};
            """
        )
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {names['cafe']} (
            id BIGINT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT NOT NULL,
            postal_code TEXT,
            lat DOUBLE PRECISION NOT NULL,
            lng DOUBLE PRECISION NOT NULL,
            category TEXT,
            hours TEXT,
            description TEXT,
            image TEXT,
            link TEXT,
            rating REAL,
            review_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS {names['review']} (
            id BIGSERIAL PRIMARY KEY,
            source_row INTEGER NOT NULL UNIQUE,
            cafe_id BIGINT NOT NULL REFERENCES {names['cafe']}(id) ON DELETE CASCADE,
            rating REAL,
            content TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS {names['cafe_embedding']} (
            cafe_id BIGINT PRIMARY KEY REFERENCES {names['cafe']}(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            embedding vector({OPENAI_EMBED_DIM}) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS {names['review_embedding']} (
            review_id BIGINT PRIMARY KEY REFERENCES {names['review']}(id) ON DELETE CASCADE,
            cafe_id BIGINT NOT NULL REFERENCES {names['cafe']}(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            embedding vector({OPENAI_EMBED_DIM}) NOT NULL
        );
        """
    )


def _upsert_base_data(cursor, dataset: CleanedCafeDataset) -> dict[int, int]:
    from psycopg2.extras import execute_values

    names = _table_names(dataset.language)
    cafe_rows = [
        (
            cafe.id,
            cafe.name,
            cafe.phone,
            cafe.address,
            cafe.postal_code,
            cafe.lat,
            cafe.lng,
            cafe.category,
            cafe.hours,
            cafe.description,
            cafe.image,
            cafe.link,
            cafe.rating,
            cafe.review_count,
        )
        for cafe in dataset.cafes
    ]
    execute_values(
        cursor,
        f"""
        INSERT INTO {names['cafe']} (
            id, name, phone, address, postal_code, lat, lng, category, hours,
            description, image, link, rating, review_count
        ) VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            phone = EXCLUDED.phone,
            address = EXCLUDED.address,
            postal_code = EXCLUDED.postal_code,
            lat = EXCLUDED.lat,
            lng = EXCLUDED.lng,
            category = EXCLUDED.category,
            hours = EXCLUDED.hours,
            description = EXCLUDED.description,
            image = EXCLUDED.image,
            link = EXCLUDED.link,
            rating = EXCLUDED.rating,
            review_count = EXCLUDED.review_count
        """,
        cafe_rows,
    )
    review_rows = [
        (review.source_row, review.cafe_id, review.rating, review.content)
        for review in dataset.reviews
    ]
    returned = execute_values(
        cursor,
        f"""
        INSERT INTO {names['review']} (source_row, cafe_id, rating, content)
        VALUES %s
        ON CONFLICT (source_row) DO UPDATE SET
            cafe_id = EXCLUDED.cafe_id,
            rating = EXCLUDED.rating,
            content = EXCLUDED.content
        RETURNING id, source_row
        """,
        review_rows,
        fetch=True,
    )
    return {source_row: review_id for review_id, source_row in returned}


def _upsert_embeddings(
    cursor,
    dataset: CleanedCafeDataset,
    review_ids: dict[int, int],
    embedder: EmbeddingClient,
) -> None:
    from psycopg2.extras import execute_values

    names = _table_names(dataset.language)
    cafe_texts = [cafe.embedding_content for cafe in dataset.cafes]
    cafe_vectors = embedder.embed(cafe_texts)
    execute_values(
        cursor,
        f"""
        INSERT INTO {names['cafe_embedding']} (cafe_id, content, embedding)
        VALUES %s
        ON CONFLICT (cafe_id) DO UPDATE SET
            content = EXCLUDED.content,
            embedding = EXCLUDED.embedding
        """,
        [
            (cafe.id, text, vector)
            for cafe, text, vector in zip(
                dataset.cafes, cafe_texts, cafe_vectors, strict=True
            )
        ],
        template="(%s, %s, %s::vector)",
    )

    review_texts = [review.content for review in dataset.reviews]
    review_vectors = embedder.embed(review_texts)
    execute_values(
        cursor,
        f"""
        INSERT INTO {names['review_embedding']}
            (review_id, cafe_id, content, embedding)
        VALUES %s
        ON CONFLICT (review_id) DO UPDATE SET
            cafe_id = EXCLUDED.cafe_id,
            content = EXCLUDED.content,
            embedding = EXCLUDED.embedding
        """,
        [
            (
                review_ids[review.source_row],
                review.cafe_id,
                text,
                vector,
            )
            for review, text, vector in zip(
                dataset.reviews, review_texts, review_vectors, strict=True
            )
        ],
        template="(%s, %s, %s, %s::vector)",
    )


def _create_indexes(cursor, language: Language) -> None:
    names = _table_names(language)
    cursor.execute(
        f"""
        CREATE INDEX IF NOT EXISTS {names['cafe_embedding']}_hnsw_idx
            ON {names['cafe_embedding']}
            USING hnsw (embedding vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS {names['review_embedding']}_hnsw_idx
            ON {names['review_embedding']}
            USING hnsw (embedding vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS {names['cafe']}_category_trgm_idx
            ON {names['cafe']} USING gin (category gin_trgm_ops);
        CREATE INDEX IF NOT EXISTS {names['review']}_cafe_id_idx
            ON {names['review']} (cafe_id);
        CREATE INDEX IF NOT EXISTS {names['review_embedding']}_cafe_id_idx
            ON {names['review_embedding']} (cafe_id);
        """
    )


def seed_datasets(
    datasets: Iterable[CleanedCafeDataset],
    *,
    rebuild: bool = False,
) -> None:
    import psycopg2

    embedder = EmbeddingClient()
    with psycopg2.connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            for dataset in datasets:
                _create_schema(cursor, dataset.language, rebuild=rebuild)
                review_ids = _upsert_base_data(cursor, dataset)
                _upsert_embeddings(cursor, dataset, review_ids, embedder)
                _create_indexes(cursor, dataset.language)


def format_report(report: CleaningReport) -> str:
    return (
        f"[{report.language}] 카페 {report.cleaned_cafes}/{report.source_cafes}, "
        f"제외 카페 {report.invalid_cafes}, "
        f"리뷰 {report.cleaned_reviews}/{report.source_reviews}, "
        f"orphan {report.orphan_reviews}, 빈 리뷰 {report.empty_reviews}, "
        f"잘못된 리뷰 {report.invalid_reviews}, "
        f"리뷰 보유 카페 {report.cafes_with_reviews}, "
        f"리뷰 없는 카페 {report.cafes_without_reviews}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_CAFE_DATA_DIR,
        help="카페 CSV가 있는 디렉터리",
    )
    parser.add_argument("--ko-cafe", type=Path, help="한국어 카페 CSV 경로")
    parser.add_argument("--ko-reviews", type=Path, help="한국어 리뷰 CSV 경로")
    parser.add_argument("--en-cafe", type=Path, help="영어 카페 CSV 경로")
    parser.add_argument("--en-reviews", type=Path, help="영어 리뷰 CSV 경로")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="CSV 정제와 검증만 수행하고 DB/API는 호출하지 않음",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="기존 카페 테이블을 제거한 뒤 다시 생성",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    defaults = CafeSeedFiles.from_directory(args.data_dir)
    datasets = load_cafe_datasets(
        CafeSeedFiles(
            ko_cafe=args.ko_cafe or defaults.ko_cafe,
            ko_reviews=args.ko_reviews or defaults.ko_reviews,
            en_cafe=args.en_cafe or defaults.en_cafe,
            en_reviews=args.en_reviews or defaults.en_reviews,
        )
    )
    for dataset in datasets:
        print(format_report(dataset.report))
    if args.dry_run:
        return
    seed_datasets(datasets, rebuild=args.rebuild)
    print("카페 및 리뷰 벡터 DB 적재가 완료되었습니다.")


if __name__ == "__main__":
    main()
