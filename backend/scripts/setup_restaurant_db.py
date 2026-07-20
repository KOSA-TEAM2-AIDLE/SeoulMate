"""Build the complete SeoulMate restaurant RAG database from committed CSV seeds.

The default mode is resumable. Use ``--reset --yes`` for a clean rebuild. Only
the 12 restaurant tables are ever dropped; tables owned by other domains are
left untouched.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import psycopg2
from dotenv import load_dotenv
from openai import OpenAI
from psycopg2 import sql
from psycopg2.errors import InvalidCatalogName
from psycopg2.extras import execute_values


BACKEND_DIR = Path(__file__).resolve().parents[1]
SEED_DIR = BACKEND_DIR / "data" / "db_seed" / "restaurant"
SCHEMA_PATH = BACKEND_DIR / "vector_db" / "restaurant" / "schema.sql"
EMBED_DIM = 1536

RESTAURANT_COLUMNS = (
    "id", "name", "phone", "address", "postal_code", "lat", "lng",
    "category", "hours", "description", "image", "link", "review_count",
    "rating", "category_kakao", "description_kakao", "last_order",
    "kakao_place_id", "kakao_place_url", "menu_price_min",
    "menu_price_median", "menu_count", "has_parking", "has_group_seating",
    "has_private_room", "has_baby_chair", "has_kids_menu", "allows_pets",
    "has_disabled_access", "hours_source",
)
MENU_COLUMNS = (
    "id", "restaurant_id", "menu_order", "menu_name", "price_text",
    "price_value", "is_main",
)
REVIEW_COLUMNS = ("id", "restaurant_id", "rating", "content")

SEEDS = {
    "restaurant_ko": ("restaurant_ko.csv", RESTAURANT_COLUMNS),
    "restaurant_en": ("restaurant_en.csv", RESTAURANT_COLUMNS),
    "restaurant_menu_ko": ("restaurant_menu_ko.csv", MENU_COLUMNS),
    "restaurant_menu_en": ("restaurant_menu_en.csv", MENU_COLUMNS),
    "restaurant_review_ko": ("restaurant_review_ko.csv", REVIEW_COLUMNS),
    "restaurant_review_en": ("restaurant_review_en.csv", REVIEW_COLUMNS),
}

DROP_ORDER = (
    "menu_embedding_en", "menu_embedding_ko",
    "review_embedding_en", "review_embedding_ko",
    "restaurant_embedding_en", "restaurant_embedding_ko",
    "restaurant_menu_en", "restaurant_menu_ko",
    "restaurant_review_en", "restaurant_review_ko",
    "restaurant_en", "restaurant_ko",
)

EMBEDDING_TABLES = (
    "restaurant_embedding_ko", "restaurant_embedding_en",
    "review_embedding_ko", "review_embedding_en",
    "menu_embedding_ko", "menu_embedding_en",
)


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "DbConfig":
        required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise RuntimeError(f".env 필수 값이 없습니다: {', '.join(missing)}")
        return cls(
            host=os.environ["DB_HOST"],
            port=int(os.environ["DB_PORT"]),
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
        )

    def kwargs(self, dbname: str | None = None) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": dbname or self.dbname,
            "user": self.user,
            "password": self.password,
            "connect_timeout": 8,
        }


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        return list(reader.fieldnames or []), list(reader)


def validate_seed_files(seed_dir: Path = SEED_DIR) -> dict[str, int]:
    """Validate headers, identifiers and language-specific foreign keys."""
    rows_by_table: dict[str, list[dict[str, str]]] = {}
    counts: dict[str, int] = {}
    for table, (filename, expected_columns) in SEEDS.items():
        path = seed_dir / filename
        if not path.exists():
            raise RuntimeError(f"시드 파일을 찾을 수 없습니다: {path}")
        header, rows = _read_csv(path)
        if tuple(header) != expected_columns:
            raise RuntimeError(
                f"{filename} 헤더가 스키마와 다릅니다.\n"
                f"expected={list(expected_columns)}\nactual={header}"
            )
        ids = [row["id"] for row in rows]
        if not rows or any(not value for value in ids):
            raise RuntimeError(f"{filename}: 비어 있거나 id가 없는 행이 있습니다.")
        if len(ids) != len(set(ids)):
            raise RuntimeError(f"{filename}: 중복 id가 있습니다.")
        rows_by_table[table] = rows
        counts[table] = len(rows)

    for lang in ("ko", "en"):
        restaurant_ids = {row["id"] for row in rows_by_table[f"restaurant_{lang}"]}
        for kind in ("menu", "review"):
            table = f"restaurant_{kind}_{lang}"
            invalid = [row["id"] for row in rows_by_table[table]
                       if row["restaurant_id"] not in restaurant_ids]
            if invalid:
                raise RuntimeError(
                    f"{table}: 존재하지 않는 restaurant_id 참조 {len(invalid)}건 "
                    f"(예: {invalid[:3]})"
                )

        for row in rows_by_table[f"restaurant_{lang}"]:
            if row["rating"] and not 0 <= float(row["rating"]) <= 5:
                raise RuntimeError(f"restaurant_{lang} id={row['id']}: 잘못된 rating")
            if row["lat"] and not -90 <= float(row["lat"]) <= 90:
                raise RuntimeError(f"restaurant_{lang} id={row['id']}: 잘못된 lat")
            if row["lng"] and not -180 <= float(row["lng"]) <= 180:
                raise RuntimeError(f"restaurant_{lang} id={row['id']}: 잘못된 lng")

    return counts


def connect_or_create_database(config: DbConfig):
    try:
        return psycopg2.connect(**config.kwargs())
    except InvalidCatalogName:
        print(f"[DB] 데이터베이스 {config.dbname!r}가 없어 생성합니다.")
        admin_db = os.getenv("DB_ADMIN_DB", "postgres")
        with psycopg2.connect(**config.kwargs(admin_db)) as admin_conn:
            admin_conn.autocommit = True
            with admin_conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(config.dbname)))
        return psycopg2.connect(**config.kwargs())


def reset_restaurant_tables(conn) -> None:
    with conn.cursor() as cur:
        for table in DROP_ORDER:
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table)))
    conn.commit()


def apply_schema(conn) -> None:
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(schema_text)
    conn.commit()


def assert_vector_dimension(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            WHERE c.relname = 'restaurant_embedding_ko'
              AND a.attname = 'embedding' AND NOT a.attisdropped
            """
        )
        row = cur.fetchone()
    if not row or row[0] != f"vector({EMBED_DIM})":
        raise RuntimeError(
            f"기존 embedding 컬럼이 vector({EMBED_DIM})가 아닙니다. "
            "setup_restaurant_db.ps1로 초기화하거나 --reset --yes를 사용하세요."
        )


def _table_count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
        return int(cur.fetchone()[0])


def load_csv_if_needed(conn, table: str, path: Path, columns: Sequence[str], expected: int) -> None:
    current = _table_count(conn, table)
    if current == expected:
        print(f"[CSV] {table}: 이미 {current:,}건, 건너뜀")
        return
    if current:
        raise RuntimeError(
            f"{table}에 {current:,}건이 있어 시드 {expected:,}건과 다릅니다. "
            "안전한 재구축을 위해 --reset --yes를 사용하세요."
        )
    copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
    )
    with path.open("r", encoding="utf-8-sig", newline="") as fp, conn.cursor() as cur:
        cur.copy_expert(copy_sql.as_string(conn), fp)
    conn.commit()
    actual = _table_count(conn, table)
    if actual != expected:
        raise RuntimeError(f"{table}: 적재 후 {actual:,}건, 예상 {expected:,}건")
    print(f"[CSV] {table}: {actual:,}건 적재 완료")


def load_all_csvs(conn, counts: dict[str, int]) -> None:
    # Parents first, then children so every FK is valid during COPY.
    order = (
        "restaurant_ko", "restaurant_en",
        "restaurant_menu_ko", "restaurant_menu_en",
        "restaurant_review_ko", "restaurant_review_en",
    )
    for table in order:
        filename, columns = SEEDS[table]
        load_csv_if_needed(conn, table, SEED_DIR / filename, columns, counts[table])


def _restaurant_pending_query(lang: str) -> str:
    restaurant = f"restaurant_{lang}"
    menu = f"restaurant_menu_{lang}"
    embedding = f"restaurant_embedding_{lang}"
    labels = (
        ("이름", "카테고리", "카카오 카테고리", "설명", "카카오 설명", "주소", "대표 메뉴")
        if lang == "ko" else
        ("Name", "Category", "Kakao category", "Description", "Kakao description", "Address", "Menus")
    )
    return f"""
        SELECT r.id, r.id,
               concat_ws(E'\\n',
                   '{labels[0]}: ' || coalesce(r.name, ''),
                   '{labels[1]}: ' || coalesce(r.category, ''),
                   '{labels[2]}: ' || coalesce(r.category_kakao, ''),
                   '{labels[3]}: ' || coalesce(r.description, ''),
                   '{labels[4]}: ' || coalesce(r.description_kakao, ''),
                   '{labels[5]}: ' || coalesce(r.address, ''),
                   '{labels[6]}: ' || coalesce(m.menu_names, '')
               ) AS content
        FROM {restaurant} r
        LEFT JOIN LATERAL (
            SELECT string_agg(x.menu_name, ', ' ORDER BY x.is_main DESC, x.menu_order) AS menu_names
            FROM (
                SELECT menu_name, is_main, menu_order
                FROM {menu}
                WHERE restaurant_id = r.id
                ORDER BY is_main DESC, menu_order
                LIMIT 10
            ) x
        ) m ON TRUE
        LEFT JOIN {embedding} e ON e.restaurant_id = r.id
        WHERE e.restaurant_id IS NULL OR e.model <> %s OR e.content <> concat_ws(E'\\n',
                   '{labels[0]}: ' || coalesce(r.name, ''),
                   '{labels[1]}: ' || coalesce(r.category, ''),
                   '{labels[2]}: ' || coalesce(r.category_kakao, ''),
                   '{labels[3]}: ' || coalesce(r.description, ''),
                   '{labels[4]}: ' || coalesce(r.description_kakao, ''),
                   '{labels[5]}: ' || coalesce(r.address, ''),
                   '{labels[6]}: ' || coalesce(m.menu_names, '')
               )
        ORDER BY r.id
    """


def pending_embedding_rows(conn, kind: str, lang: str, model: str) -> list[tuple[int, int, str]]:
    if kind == "restaurant":
        query = _restaurant_pending_query(lang)
    elif kind == "review":
        query = f"""
            SELECT s.id, s.restaurant_id, s.content
            FROM restaurant_review_{lang} s
            LEFT JOIN review_embedding_{lang} e ON e.review_id = s.id
            WHERE e.review_id IS NULL OR e.model <> %s OR e.content <> s.content
            ORDER BY s.id
        """
    elif kind == "menu":
        query = f"""
            SELECT s.id, s.restaurant_id, s.menu_name
            FROM restaurant_menu_{lang} s
            LEFT JOIN menu_embedding_{lang} e ON e.menu_id = s.id
            WHERE e.menu_id IS NULL OR e.model <> %s OR e.content <> s.menu_name
            ORDER BY s.id
        """
    else:
        raise ValueError(kind)
    with conn.cursor() as cur:
        cur.execute(query, (model,))
        return [(int(a), int(b), str(c)) for a, b, c in cur.fetchall()]


def request_embeddings(client: OpenAI, model: str, texts: list[str], retries: int = 4) -> list[list[float]]:
    for attempt in range(retries):
        try:
            response = client.embeddings.create(
                model=model,
                input=texts,
                dimensions=EMBED_DIM,
            )
            vectors = [item.embedding for item in response.data]
            if len(vectors) != len(texts) or any(len(v) != EMBED_DIM for v in vectors):
                raise RuntimeError("OpenAI embedding 응답 개수 또는 차원이 올바르지 않습니다.")
            return vectors
        except Exception:
            if attempt == retries - 1:
                raise
            delay = 2 ** attempt
            print(f"[EMBED] 요청 실패, {delay}초 후 재시도 ({attempt + 1}/{retries})")
            time.sleep(delay)
    raise AssertionError("unreachable")


def _vector_literal(vector: Iterable[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


def upsert_embedding_batch(
    conn, kind: str, lang: str, model: str,
    rows: Sequence[tuple[int, int, str]], vectors: Sequence[Sequence[float]],
) -> None:
    table = f"{kind}_embedding_{lang}"
    if kind == "restaurant":
        values = [(restaurant_id, content, model, _vector_literal(vector))
                  for (_, restaurant_id, content), vector in zip(rows, vectors)]
        query = f"""
            INSERT INTO {table} (restaurant_id, content, model, embedding, updated_at)
            VALUES %s
            ON CONFLICT (restaurant_id) DO UPDATE SET
                content = EXCLUDED.content, model = EXCLUDED.model,
                embedding = EXCLUDED.embedding, updated_at = now()
        """
        template = "(%s,%s,%s,%s::vector,now())"
    else:
        key = "review_id" if kind == "review" else "menu_id"
        values = [(source_id, restaurant_id, content, model, _vector_literal(vector))
                  for (source_id, restaurant_id, content), vector in zip(rows, vectors)]
        query = f"""
            INSERT INTO {table} ({key}, restaurant_id, content, model, embedding, updated_at)
            VALUES %s
            ON CONFLICT ({key}) DO UPDATE SET
                restaurant_id = EXCLUDED.restaurant_id, content = EXCLUDED.content,
                model = EXCLUDED.model, embedding = EXCLUDED.embedding, updated_at = now()
        """
        template = "(%s,%s,%s,%s,%s::vector,now())"
    with conn.cursor() as cur:
        execute_values(cur, query, values, template=template, page_size=len(values))
    conn.commit()


def build_embeddings(conn, model: str, batch_size: int) -> None:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    for lang in ("ko", "en"):
        for kind in ("restaurant", "review", "menu"):
            rows = pending_embedding_rows(conn, kind, lang, model)
            total = len(rows)
            if not total:
                print(f"[EMBED] {kind}_{lang}: 최신 상태")
                continue
            print(f"[EMBED] {kind}_{lang}: {total:,}건 생성")
            for start in range(0, total, batch_size):
                batch = rows[start:start + batch_size]
                # Character cap protects the embedding endpoint from accidental huge reviews.
                texts = [content[:12_000] for _, _, content in batch]
                vectors = request_embeddings(client, model, texts)
                normalized_rows = [(a, b, text) for (a, b, _), text in zip(batch, texts)]
                upsert_embedding_batch(conn, kind, lang, model, normalized_rows, vectors)
                print(f"         {min(start + len(batch), total):,}/{total:,}")


def create_vector_indexes(conn) -> None:
    print("[INDEX] HNSW cosine 인덱스를 확인합니다.")
    with conn.cursor() as cur:
        for table in EMBEDDING_TABLES:
            index = f"{table}_hnsw_cosine_idx"
            cur.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} USING hnsw (embedding vector_cosine_ops)")
                .format(sql.Identifier(index), sql.Identifier(table))
            )
        cur.execute("ANALYZE")
    conn.commit()


def verify_database(conn, seed_counts: dict[str, int], require_embeddings: bool = True) -> dict[str, int]:
    result: dict[str, int] = {}
    for table, expected in seed_counts.items():
        actual = _table_count(conn, table)
        result[table] = actual
        if actual != expected:
            raise RuntimeError(f"검증 실패: {table}={actual:,}, CSV={expected:,}")

    if require_embeddings:
        sources = {
            "restaurant_embedding_ko": "restaurant_ko",
            "restaurant_embedding_en": "restaurant_en",
            "review_embedding_ko": "restaurant_review_ko",
            "review_embedding_en": "restaurant_review_en",
            "menu_embedding_ko": "restaurant_menu_ko",
            "menu_embedding_en": "restaurant_menu_en",
        }
        with conn.cursor() as cur:
            for embedding_table, source_table in sources.items():
                actual = _table_count(conn, embedding_table)
                expected = _table_count(conn, source_table)
                result[embedding_table] = actual
                if actual != expected:
                    raise RuntimeError(
                        f"검증 실패: {embedding_table}={actual:,}, {source_table}={expected:,}"
                    )
                cur.execute(
                    sql.SQL("SELECT COUNT(*) FROM {} WHERE vector_dims(embedding) <> %s")
                    .format(sql.Identifier(embedding_table)),
                    (EMBED_DIM,),
                )
                if cur.fetchone()[0]:
                    raise RuntimeError(f"검증 실패: {embedding_table}에 차원이 다른 벡터가 있습니다.")
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SeoulMate 식당 RAG DB 전체 구축")
    parser.add_argument("--reset", action="store_true", help="식당 관련 12개 테이블을 다시 만듭니다.")
    parser.add_argument("--yes", action="store_true", help="reset 확인 질문을 생략합니다.")
    parser.add_argument("--skip-embeddings", action="store_true", help="CSV 테이블만 적재합니다.")
    parser.add_argument("--validate-only", action="store_true", help="CSV만 검증하고 DB에는 접속하지 않습니다.")
    parser.add_argument("--verify-only", action="store_true", help="CSV와 현재 DB 건수/벡터만 검증합니다.")
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("EMBED_BATCH_SIZE", "100")))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv(BACKEND_DIR / ".env")
    args = parse_args(argv)
    if int(os.getenv("OPENAI_EMBED_DIM", str(EMBED_DIM))) != EMBED_DIM:
        raise RuntimeError(f"OPENAI_EMBED_DIM은 현재 스키마 계약상 {EMBED_DIM}이어야 합니다.")
    if args.batch_size < 1 or args.batch_size > 500:
        raise RuntimeError("batch-size는 1~500이어야 합니다.")

    print(f"[VALIDATE] CSV 경로: {SEED_DIR}")
    counts = validate_seed_files()
    for table, count in counts.items():
        print(f"           {table}: {count:,}건")
    if args.validate_only:
        print("[DONE] CSV 검증 완료")
        return 0

    if not args.skip_embeddings and not args.verify_only and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(".env에 OPENAI_API_KEY를 설정하세요.")
    model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")
    config = DbConfig.from_env()

    if args.reset and not args.yes:
        answer = input("식당 관련 12개 테이블을 삭제 후 재생성합니다. 계속할까요? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("취소했습니다.")
            return 1

    with connect_or_create_database(config) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (2026071701,))
        try:
            if args.verify_only:
                assert_vector_dimension(conn)
                summary = verify_database(conn, counts, require_embeddings=not args.skip_embeddings)
            else:
                if args.reset:
                    print("[DB] 식당 관련 테이블만 초기화합니다.")
                    reset_restaurant_tables(conn)
                apply_schema(conn)
                assert_vector_dimension(conn)
                load_all_csvs(conn, counts)
                if not args.skip_embeddings:
                    build_embeddings(conn, model, args.batch_size)
                    create_vector_indexes(conn)
                summary = verify_database(conn, counts, require_embeddings=not args.skip_embeddings)
        finally:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (2026071701,))
            conn.commit()

    print("\n[DONE] 식당 DB 구축 및 검증 완료")
    for table, count in summary.items():
        print(f"       {table}: {count:,}건")
    if args.skip_embeddings:
        print("[NOTICE] 임베딩을 생략했으므로 식당 RAG 검색은 아직 사용할 수 없습니다.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n중단되었습니다. --reset 없이 다시 실행하면 완료된 임베딩 다음부터 이어집니다.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
