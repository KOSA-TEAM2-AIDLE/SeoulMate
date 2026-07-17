"""관광지·행사·리뷰를 언어별 PostgreSQL/pgvector 테이블에 적재한다.

데이터만 검증:
    uv run python -m vector_db.attraction.seed_vectordb --dry-run

신규 관광 테이블을 재생성해 적재:
    uv run python -m vector_db.attraction.seed_vectordb --rebuild
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator, Literal, Sequence

from core.config import (
    DATA_DIR,
    DB_CONFIG,
    OPENAI_API_KEY,
    OPENAI_EMBED_DIM,
    OPENAI_EMBED_MODEL,
)
from scripts.data_pipeline.attraction.models import CleanedAttractionDataset
from scripts.data_pipeline.attraction.dataset import clean_attraction_datasets


Language = Literal["ko", "en"]
DEFAULT_BATCH_SIZE = 200
ATTRACTION_DATA_DIR = DATA_DIR / "attraction"


def _table_names(language: Language) -> dict[str, str]:
    if language not in {"ko", "en"}:
        raise ValueError(f"지원하지 않는 관광 데이터 언어입니다: {language}")
    return {
        "attraction": f"attraction_{language}",
        "review": f"attraction_review_{language}",
        "attraction_embedding": f"attraction_embedding_{language}",
        "review_embedding": f"attraction_review_embedding_{language}",
    }


def create_schema(cursor, language: Language, *, rebuild: bool = False) -> None:
    """언어별 원본·리뷰·임베딩 테이블을 생성한다.

    이 함수는 dry-run에서 호출하지 않는다.
    """
    names = _table_names(language)
    if rebuild:
        cursor.execute(
            f"""
            DROP TABLE IF EXISTS {names['review_embedding']};
            DROP TABLE IF EXISTS {names['attraction_embedding']};
            DROP TABLE IF EXISTS {names['review']};
            DROP TABLE IF EXISTS {names['attraction']};
            """
        )

    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {names['attraction']} (
            id TEXT PRIMARY KEY,
            source_cid TEXT NOT NULL UNIQUE,
            language TEXT NOT NULL CHECK (language IN ('ko', 'en')),
            kind TEXT NOT NULL CHECK (kind IN ('attraction', 'event')),
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            category_primary TEXT NOT NULL DEFAULT '',
            category_secondary TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            hours TEXT NOT NULL DEFAULT '',
            fee TEXT NOT NULL DEFAULT '',
            image TEXT,
            link TEXT,
            start_date DATE,
            end_date DATE,
            rating REAL CHECK (rating IS NULL OR rating BETWEEN 0 AND 5),
            review_count INTEGER NOT NULL DEFAULT 0 CHECK (review_count >= 0),
            english_review_count INTEGER NOT NULL DEFAULT 0
                CHECK (english_review_count >= 0),
            foreign_review_count INTEGER NOT NULL DEFAULT 0
                CHECK (foreign_review_count >= 0),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS {names['review']} (
            id BIGSERIAL PRIMARY KEY,
            source_review_id TEXT NOT NULL,
            attraction_id TEXT NOT NULL
                REFERENCES {names['attraction']}(id) ON DELETE CASCADE,
            language TEXT NOT NULL CHECK (language IN ('ko', 'en')),
            rating REAL CHECK (rating IS NULL OR rating BETWEEN 0 AND 5),
            content TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (source_review_id, attraction_id)
        );

        CREATE TABLE IF NOT EXISTS {names['attraction_embedding']} (
            attraction_id TEXT PRIMARY KEY
                REFERENCES {names['attraction']}(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            embedding vector({OPENAI_EMBED_DIM}) NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS {names['review_embedding']} (
            review_id BIGINT PRIMARY KEY
                REFERENCES {names['review']}(id) ON DELETE CASCADE,
            attraction_id TEXT NOT NULL
                REFERENCES {names['attraction']}(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            embedding vector({OPENAI_EMBED_DIM}) NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


def format_dry_run_report(datasets) -> str:
    return json.dumps(
        {
            "mode": "dry-run",
            "database_written": False,
            "embedding_api_called": False,
            "embedding_dimension": OPENAI_EMBED_DIM,
            "datasets": [asdict(dataset.report) for dataset in datasets],
            "totals": {
                "places": sum(len(dataset.places) for dataset in datasets),
                "reviews": sum(len(dataset.reviews) for dataset in datasets),
                "embedding_documents": sum(
                    len(dataset.places) + len(dataset.reviews)
                    for dataset in datasets
                ),
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def _batched(items: Sequence, size: int) -> Iterator[Sequence]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class EmbeddingClient:
    def __init__(self, *, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        from openai import OpenAI

        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
        if batch_size <= 0:
            raise ValueError("batch_size는 0보다 커야 합니다.")
        self._client = OpenAI(api_key=OPENAI_API_KEY)
        self._batch_size = batch_size

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for batch in _batched(texts, self._batch_size):
            response = self._client.embeddings.create(
                model=OPENAI_EMBED_MODEL,
                input=list(batch),
                dimensions=OPENAI_EMBED_DIM,
            )
            vectors.extend(item.embedding for item in response.data)
        if len(vectors) != len(texts):
            raise RuntimeError("임베딩 응답 수가 입력 문서 수와 다릅니다.")
        return vectors


def upsert_base_data(
    cursor,
    dataset: CleanedAttractionDataset,
) -> dict[tuple[str, str], int]:
    from psycopg2.extras import execute_values

    names = _table_names(dataset.language)
    execute_values(
        cursor,
        f"""
        INSERT INTO {names['attraction']} (
            id, source_cid, language, kind, name, category,
            category_primary, category_secondary, summary, description,
            tags, address, latitude, longitude, hours, fee, image, link,
            start_date, end_date, rating, review_count,
            english_review_count, foreign_review_count
        ) VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            source_cid = EXCLUDED.source_cid,
            language = EXCLUDED.language,
            kind = EXCLUDED.kind,
            name = EXCLUDED.name,
            category = EXCLUDED.category,
            category_primary = EXCLUDED.category_primary,
            category_secondary = EXCLUDED.category_secondary,
            summary = EXCLUDED.summary,
            description = EXCLUDED.description,
            tags = EXCLUDED.tags,
            address = EXCLUDED.address,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            hours = EXCLUDED.hours,
            fee = EXCLUDED.fee,
            image = EXCLUDED.image,
            link = EXCLUDED.link,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date,
            rating = EXCLUDED.rating,
            review_count = EXCLUDED.review_count,
            english_review_count = EXCLUDED.english_review_count,
            foreign_review_count = EXCLUDED.foreign_review_count,
            updated_at = NOW()
        """,
        [
            (
                place.id, place.source_cid, place.language, place.kind,
                place.name, place.category, place.category_primary,
                place.category_secondary, place.summary, place.description,
                place.tags, place.address, place.latitude, place.longitude,
                place.hours, place.fee, place.image, place.link,
                place.start_date, place.end_date, place.rating,
                place.review_count, place.english_review_count,
                place.foreign_review_count,
            )
            for place in dataset.places
        ],
        page_size=500,
    )

    returned = execute_values(
        cursor,
        f"""
        INSERT INTO {names['review']} (
            source_review_id, attraction_id, language, rating, content
        ) VALUES %s
        ON CONFLICT (source_review_id, attraction_id) DO UPDATE SET
            language = EXCLUDED.language,
            rating = EXCLUDED.rating,
            content = EXCLUDED.content,
            updated_at = NOW()
        RETURNING id, source_review_id, attraction_id
        """,
        [
            (
                review.source_review_id, review.attraction_id,
                review.language, review.rating, review.content,
            )
            for review in dataset.reviews
        ],
        page_size=500,
        fetch=True,
    )
    return {
        (str(source_review_id), str(attraction_id)): int(review_id)
        for review_id, source_review_id, attraction_id in returned
    }


def upsert_embeddings(
    cursor,
    dataset: CleanedAttractionDataset,
    review_ids: dict[tuple[str, str], int],
    embedder: EmbeddingClient,
) -> dict[str, int]:
    from psycopg2.extras import execute_values

    names = _table_names(dataset.language)
    place_contents = [place.embedding_content for place in dataset.places]
    place_vectors = embedder.embed(place_contents)
    execute_values(
        cursor,
        f"""
        INSERT INTO {names['attraction_embedding']} (
            attraction_id, content, content_hash, embedding
        ) VALUES %s
        ON CONFLICT (attraction_id) DO UPDATE SET
            content = EXCLUDED.content,
            content_hash = EXCLUDED.content_hash,
            embedding = EXCLUDED.embedding,
            updated_at = NOW()
        """,
        [
            (place.id, content, _content_hash(content), vector)
            for place, content, vector in zip(
                dataset.places, place_contents, place_vectors, strict=True
            )
        ],
        template="(%s, %s, %s, %s::vector)",
        page_size=500,
    )

    review_contents = [review.content for review in dataset.reviews]
    review_vectors = embedder.embed(review_contents)
    execute_values(
        cursor,
        f"""
        INSERT INTO {names['review_embedding']} (
            review_id, attraction_id, content, content_hash, embedding
        ) VALUES %s
        ON CONFLICT (review_id) DO UPDATE SET
            attraction_id = EXCLUDED.attraction_id,
            content = EXCLUDED.content,
            content_hash = EXCLUDED.content_hash,
            embedding = EXCLUDED.embedding,
            updated_at = NOW()
        """,
        [
            (
                review_ids[(review.source_review_id, review.attraction_id)],
                review.attraction_id, content, _content_hash(content), vector,
            )
            for review, content, vector in zip(
                dataset.reviews, review_contents, review_vectors, strict=True
            )
        ],
        template="(%s, %s, %s, %s, %s::vector)",
        page_size=500,
    )
    return {"places": len(place_vectors), "reviews": len(review_vectors)}


def create_indexes(cursor, language: Language) -> None:
    names = _table_names(language)
    cursor.execute(
        f"""
        CREATE INDEX IF NOT EXISTS {names['attraction_embedding']}_hnsw_idx
            ON {names['attraction_embedding']}
            USING hnsw (embedding vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS {names['review_embedding']}_hnsw_idx
            ON {names['review_embedding']}
            USING hnsw (embedding vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS {names['attraction']}_category_trgm_idx
            ON {names['attraction']} USING gin (category gin_trgm_ops);
        CREATE INDEX IF NOT EXISTS {names['attraction']}_kind_idx
            ON {names['attraction']} (kind);
        CREATE INDEX IF NOT EXISTS {names['review']}_attraction_id_idx
            ON {names['review']} (attraction_id);
        CREATE INDEX IF NOT EXISTS {names['review_embedding']}_attraction_id_idx
            ON {names['review_embedding']} (attraction_id);
        """
    )


def rebuild_datasets(
    datasets: Iterable[CleanedAttractionDataset],
    *,
    batch_size: int,
) -> dict[str, dict[str, int]]:
    import psycopg2

    embedder = EmbeddingClient(batch_size=batch_size)
    results: dict[str, dict[str, int]] = {}
    with psycopg2.connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            # 기존 관광 단일 Vector Document 구조도 같은
            # 트랜잭션 안에서 제거한다. 적재가 실패하면 삭제도 롤백된다.
            cursor.execute("DROP TABLE IF EXISTS attraction_vector_documents;")
            for dataset in datasets:
                language = dataset.language
                create_schema(cursor, language, rebuild=True)
                review_ids = upsert_base_data(cursor, dataset)
                embedded = upsert_embeddings(
                    cursor, dataset, review_ids, embedder
                )
                create_indexes(cursor, language)
                results[language] = {
                    "places": len(dataset.places),
                    "reviews": len(dataset.reviews),
                    "place_embeddings": embedded["places"],
                    "review_embeddings": embedded["reviews"],
                }
    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ATTRACTION_DATA_DIR,
        help="관광 raw 폴더가 있는 데이터 경로",
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=date.today(),
        help="행사 종료일 필터 기준일(YYYY-MM-DD)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="한 번에 처리할 임베딩 문서 수",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB와 OpenAI를 호출하지 않고 정제 통계만 출력",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="신규 언어별 관광 테이블을 재생성",
    )
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size는 0보다 커야 합니다.")
    if args.dry_run and args.rebuild:
        parser.error("--dry-run과 --rebuild는 동시에 사용할 수 없습니다.")
    return args


def main() -> None:
    args = _parse_args()
    datasets = clean_attraction_datasets(args.data_dir, args.as_of)
    if args.dry_run:
        print(format_dry_run_report(datasets))
        return
    if not args.rebuild:
        raise ValueError(
            "현재 적재기는 안전한 전체 재구축만 지원합니다. "
            "--rebuild를 사용해 주세요."
        )
    result = rebuild_datasets(datasets, batch_size=args.batch_size)
    print(json.dumps({"mode": "rebuild", "datasets": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


__all__ = [
    "EmbeddingClient",
    "create_indexes",
    "create_schema",
    "format_dry_run_report",
    "rebuild_datasets",
    "upsert_base_data",
    "upsert_embeddings",
]
