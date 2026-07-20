def create_table_sql(embedding_dim: int) -> str:
    if embedding_dim <= 0:
        raise ValueError("embedding_dim은 양수여야 합니다")
    return f"""
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS attraction_vector_documents (
        document_id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        metadata JSONB NOT NULL,
        content_hash TEXT NOT NULL,
        embedding vector({embedding_dim}) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS attraction_vector_documents_embedding_idx
        ON attraction_vector_documents USING ivfflat (embedding vector_cosine_ops);
    """
