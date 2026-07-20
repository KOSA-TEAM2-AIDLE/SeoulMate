import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
ACCOMMODATION_CSV = "data/db_seed/accommodation/tripadvisor_cleaned_result_en.csv"

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 1536  # Matryoshka reduction
BATCH_SIZE = 200  # Batch size for embedding calls

DB_PARAMS = {
    "host": "localhost",
    "port": 5433,
    "user": "seoulmate",
    "password": "1234",
    "database": "seoulmate",
}

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
print("Configuration completed.")


def embed_batch(texts):
    """Convert text list -> 1536-dim vector list (Batch API call)"""
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIM,
    )
    return [d.embedding for d in resp.data]


def embed_all(texts):
    """Split all texts by BATCH_SIZE and generate embeddings"""
    vectors = []
    total = len(texts)
    for i in range(0, total, BATCH_SIZE):
        chunk = texts[i : i + BATCH_SIZE]
        vectors.extend(embed_batch(chunk))
        print(f"   Embedding progress: {min(i + BATCH_SIZE, total)}/{total}")
    return vectors


def build_accommodation_content(row):
    """Constructs descriptive text for hotel embedding using exact Korean CSV headers"""
    parts = []
    if pd.notna(row["호텔명"]):
        parts.append(str(row["호텔명"]).strip())
    if pd.notna(row["호텔 스타일"]):
        parts.append(f"Style: {str(row['호텔 스타일']).strip()}")
    if pd.notna(row["소개"]):
        parts.append(str(row["소개"]).strip())

    text = ". ".join(parts).strip()
    if not text:
        text = "Accommodation"
    return text


def parse_int_with_comma(val):
    """Safely converts string with thousand separators (e.g., '1,582') to integer"""
    if pd.isna(val):
        return 0
    cleaned = str(val).replace(",", "").strip()
    try:
        return int(cleaned)
    except ValueError:
        try:
            return int(float(cleaned))
        except ValueError:
            return 0


def main():
    print("Loading and preprocessing data...")
    df = pd.read_csv(ACCOMMODATION_CSV, encoding="utf-8-sig")

    print(f"Original data loaded: Total {len(df)} accommodation records")

    print("Connecting to database and creating tables...")
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    # Install pgvector and pg_trgm extensions
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # Drop existing tables to initialize database schema (_en applied)
    cur.execute("DROP TABLE IF EXISTS acc_review_embedding_en;")
    cur.execute("DROP TABLE IF EXISTS accommodation_embedding_en;")
    cur.execute("DROP TABLE IF EXISTS accommodation_review_en;")
    cur.execute("DROP TABLE IF EXISTS accommodation_en;")

    # Define base accommodation table schema (_en)
    cur.execute("""
        CREATE TABLE accommodation_en (
            id               BIGINT PRIMARY KEY,
            name             TEXT,
            address          TEXT,
            lat              DOUBLE PRECISION,
            lng              DOUBLE PRECISION,
            rating           REAL,
            hotel_style      TEXT,
            languages        TEXT,
            description      TEXT,
            amenities        TEXT,
            room_features    TEXT,
            room_types       TEXT,
            image            TEXT,
            link             TEXT,
            review_count     INTEGER
        );
    """)

    # Define 1:N review table schema (_en)
    cur.execute("""
        CREATE TABLE accommodation_review_en (
            id               SERIAL PRIMARY KEY,
            accommodation_id BIGINT,
            content          TEXT
        );
    """)

    # Define vector vector embedding tables (_en)
    cur.execute(f"""
        CREATE TABLE accommodation_embedding_en (
            id               SERIAL PRIMARY KEY,
            accommodation_id BIGINT,
            content          TEXT,
            embedding        vector({EMBEDDING_DIM})
        );
    """)
    cur.execute(f"""
        CREATE TABLE acc_review_embedding_en (
            id               SERIAL PRIMARY KEY,
            accommodation_id BIGINT,
            content          TEXT,
            embedding        vector({EMBEDDING_DIM})
        );
    """)
    conn.commit()
    print("Tables created successfully.")

    # 1. Map and parse rows for base hotel table using exact Korean headers
    print("Processing and inserting accommodation data...")
    acc_rows = []
    for _, row in df.iterrows():
        acc_rows.append(
            (
                int(row["id"]),
                row["호텔명"] if pd.notna(row["호텔명"]) else None,
                row["도로명주소"] if pd.notna(row["도로명주소"]) else None,
                float(row["위도"]) if pd.notna(row["위도"]) else None,
                float(row["경도"]) if pd.notna(row["경도"]) else None,
                float(row["평점"]) if pd.notna(row["평점"]) else None,
                row["호텔 스타일"] if pd.notna(row["호텔 스타일"]) else None,
                row["직원 사용 언어"] if pd.notna(row["직원 사용 언어"]) else None,
                row["소개"] if pd.notna(row["소개"]) else None,
                row["편의 시설"] if pd.notna(row["편의 시설"]) else None,
                row["객실 특징"] if pd.notna(row["객실 특징"]) else None,
                row["객실 유형"] if pd.notna(row["객실 유형"]) else None,
                row["이미지"] if pd.notna(row["이미지"]) else None,
                row["링크"] if pd.notna(row["링크"]) else None,
                parse_int_with_comma(row["리뷰 갯수"]),
            )
        )

    acc_cols = [
        "id",
        "name",
        "address",
        "lat",
        "lng",
        "rating",
        "hotel_style",
        "languages",
        "description",
        "amenities",
        "room_features",
        "room_types",
        "image",
        "link",
        "review_count",
    ]
    execute_values(
        cur, f"INSERT INTO accommodation_en ({', '.join(acc_cols)}) VALUES %s", acc_rows
    )

    # 2. Normalize horizontally aligned reviews into vertical rows (Melting) using Korean headers
    print("Normalizing and inserting review data...")
    rev_rows = []
    review_cols = [f"리뷰_{i}" for i in range(1, 21) if f"리뷰_{i}" in df.columns]

    for _, row in df.iterrows():
        acc_id = int(row["id"])
        for col in review_cols:
            content = row[col]
            if pd.notna(content) and str(content).strip():
                rev_rows.append((acc_id, str(content).strip()))

    execute_values(
        cur,
        "INSERT INTO accommodation_review_en (accommodation_id, content) VALUES %s",
        rev_rows,
    )
    conn.commit()
    print(
        f"Main tables populated: Hotels {len(acc_rows)} records, Normalized reviews {len(rev_rows)} records."
    )

    # 3. Generate & store main hotel description embeddings
    print(f"Generating accommodation vectors ({len(df)})...")
    acc_ids = df["id"].tolist()
    acc_texts = [build_accommodation_content(row) for _, row in df.iterrows()]
    acc_vectors = embed_all(acc_texts)

    acc_data = [
        (aid, txt, vec) for aid, txt, vec in zip(acc_ids, acc_texts, acc_vectors)
    ]
    execute_values(
        cur,
        "INSERT INTO accommodation_embedding_en (accommodation_id, content, embedding) VALUES %s",
        acc_data,
        template="(%s, %s, %s::vector)",
    )
    conn.commit()
    print("Accommodation vectors saved successfully.")

    # 4. Generate & store split review embeddings
    print(f"Generating review vectors ({len(rev_rows)})...")
    rev_ids = [r[0] for r in rev_rows]
    rev_texts = [r[1] for r in rev_rows]
    rev_vectors = embed_all(rev_texts)

    rev_data = [
        (aid, txt, vec) for aid, txt, vec in zip(rev_ids, rev_texts, rev_vectors)
    ]
    execute_values(
        cur,
        "INSERT INTO acc_review_embedding_en (accommodation_id, content, embedding) VALUES %s",
        rev_data,
        template="(%s, %s, %s::vector)",
    )
    conn.commit()
    print("Review vectors saved successfully.")

    # 5. Create database optimization indexes
    print("Creating indexing systems...")
    cur.execute(
        "CREATE INDEX ON accommodation_embedding_en USING hnsw (embedding vector_cosine_ops);"
    )
    cur.execute(
        "CREATE INDEX ON acc_review_embedding_en USING hnsw (embedding vector_cosine_ops);"
    )
    cur.execute(
        "CREATE INDEX ON accommodation_en USING gin (hotel_style gin_trgm_ops);"
    )
    cur.execute("CREATE INDEX ON accommodation_embedding_en (accommodation_id);")
    cur.execute("CREATE INDEX ON acc_review_embedding_en (accommodation_id);")
    cur.execute("CREATE INDEX ON accommodation_review_en (accommodation_id);")
    conn.commit()
    print("Indexes built successfully.")

    # Final verification of row count ingestion
    print("\n[Data Ingestion Verification]")
    for tbl in [
        "accommodation_en",
        "accommodation_review_en",
        "accommodation_embedding_en",
        "acc_review_embedding_en",
    ]:
        cur.execute(f"SELECT COUNT(*) FROM {tbl};")
        print(f"- {tbl}: {cur.fetchone()[0]} rows successfully ingested.")

    cur.close()
    conn.close()
    print(
        "\nDone! Data type adjustments and vector ingestion are finalized for English pipeline."
    )


if __name__ == "__main__":
    main()
