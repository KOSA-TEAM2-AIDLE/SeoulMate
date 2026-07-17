import json
from datetime import date
from typing import Any

import psycopg2

from core.config import DB_CONFIG, OPENAI_EMBED_DIM
from scripts.data_pipeline.attraction.models import RAGDocument
from vector_db.attraction.schema import create_table_sql


class AttractionVectorRepository:
    def __init__(self, connection_factory=None) -> None:
        self._connection_factory = connection_factory or (lambda: psycopg2.connect(**DB_CONFIG))

    def initialize(self) -> None:
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(create_table_sql(OPENAI_EMBED_DIM))

    def existing_hashes(self, document_ids: list[str]) -> dict[str, str]:
        if not document_ids:
            return {}
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT document_id, content_hash FROM attraction_vector_documents WHERE document_id = ANY(%s)",
                (document_ids,),
            )
            return dict(cursor.fetchall())

    def upsert(self, documents: list[RAGDocument], vectors: list[list[float]]) -> None:
        if len(documents) != len(vectors):
            raise ValueError("문서와 임베딩 개수가 다릅니다.")
        rows = [
            (doc.document_id, doc.content, json.dumps(doc.metadata, ensure_ascii=False), doc.content_hash, json.dumps(vector))
            for doc, vector in zip(documents, vectors, strict=True)
        ]
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO attraction_vector_documents (document_id, content, metadata, content_hash, embedding)
                VALUES (%s, %s, %s::jsonb, %s, %s::vector)
                ON CONFLICT (document_id) DO UPDATE SET
                    content = EXCLUDED.content, metadata = EXCLUDED.metadata,
                    content_hash = EXCLUDED.content_hash, embedding = EXCLUDED.embedding,
                    updated_at = NOW()
                """,
                rows,
            )

    def search_profiles(
        self,
        vector: list[float],
        *,
        language: str,
        as_of: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit은 양수여야 합니다.")
        sql = """
            WITH active_profiles AS (
                SELECT document_id, content, metadata, embedding
                FROM attraction_vector_documents
                WHERE metadata->>'lang' = %s
                  AND metadata->>'kind' IN ('attraction', 'event')
                  AND (
                        metadata->>'kind' = 'attraction'
                        OR metadata->>'end_date' = ''
                        OR metadata->>'end_date' >= %s
                      )
            )
            SELECT document_id, content, metadata, embedding <=> %s::vector AS distance
            FROM active_profiles
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        vector_json = json.dumps(vector)
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(sql, (language, as_of.isoformat(), vector_json, vector_json, limit))
            return [self._search_row(row) for row in cursor.fetchall()]

    def search_reviews(
        self,
        vector: list[float],
        *,
        language: str,
        place_keys: list[str],
        limit_per_place: int,
    ) -> list[dict[str, Any]]:
        if not place_keys:
            return []
        if limit_per_place <= 0:
            raise ValueError("limit_per_place는 양수여야 합니다.")
        sql = """
            WITH selected_reviews AS (
                SELECT document_id, content, metadata, embedding
                FROM attraction_vector_documents
                WHERE metadata->>'lang' = %s
                  AND metadata->>'kind' = 'review'
                  AND metadata->>'place_key' = ANY(%s)
            ), ranked_reviews AS (
                SELECT
                    document_id,
                    content,
                    metadata,
                    embedding <=> %s::vector AS distance,
                    ROW_NUMBER() OVER (
                        PARTITION BY metadata->>'place_key'
                        ORDER BY embedding <=> %s::vector
                    ) AS place_rank
                FROM selected_reviews
            )
            SELECT document_id, content, metadata, distance
            FROM ranked_reviews
            WHERE place_rank <= %s
            ORDER BY distance
        """
        vector_json = json.dumps(vector)
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(sql, (language, place_keys, vector_json, vector_json, limit_per_place))
            return [self._search_row(row) for row in cursor.fetchall()]

    @staticmethod
    def _search_row(row: tuple[Any, Any, Any, Any]) -> dict[str, Any]:
        document_id, content, metadata, distance = row
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return {
            "document_id": document_id,
            "content": content,
            "metadata": metadata,
            "distance": float(distance),
        }
