import json

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
