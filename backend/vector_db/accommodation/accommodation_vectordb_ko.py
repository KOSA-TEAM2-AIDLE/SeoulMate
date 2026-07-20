import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- 설정 ---
ACCOMMODATION_CSV = "data/db_seed/accommodation/tripadvisor_cleaned_result.csv"

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 1536  # Matryoshka 축소
BATCH_SIZE = 200  # 배치 임베딩 크기

DB_PARAMS = {
    "host": "localhost",
    "port": 5433,
    "user": "seoulmate",
    "password": "1234",
    "database": "seoulmate",
}

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
print("설정 완료")


def embed_batch(texts):
    """텍스트 리스트 -> 1536차원 벡터 리스트 (배치 호출)"""
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIM,
    )
    return [d.embedding for d in resp.data]


def embed_all(texts):
    """전체 텍스트를 BATCH_SIZE씩 나눠 임베딩"""
    vectors = []
    total = len(texts)
    for i in range(0, total, BATCH_SIZE):
        chunk = texts[i : i + BATCH_SIZE]
        vectors.extend(embed_batch(chunk))
        print(f"   임베딩 진행: {min(i + BATCH_SIZE, total)}/{total}")
    return vectors


def build_accommodation_content(row):
    """숙소 임베딩용 텍스트 빌더 (제공된 CSV 컬럼명 기준)"""
    parts = []
    if pd.notna(row["호텔명"]):
        parts.append(str(row["호텔명"]).strip())
    if pd.notna(row["호텔 스타일"]):
        parts.append(f"스타일: {str(row['호텔 스타일']).strip()}")
    if pd.notna(row["소개"]):
        parts.append(str(row["소개"]).strip())

    text = ". ".join(parts).strip()
    if not text:
        text = "숙박시설"
    return text


def parse_int_with_comma(val):
    """'1,582' 같은 천 단위 콤마가 포함된 문자열을 안전하게 int로 변환"""
    if pd.isna(val):
        return 0
    # 문자열 처리 후 숫자가 아닌 찌꺼기 제거 및 콤마 제거
    cleaned = str(val).replace(",", "").strip()
    try:
        return int(cleaned)
    except ValueError:
        # 혹시 실수형태('1582.0')로 인지될 경우를 대비한 2차 예외 처리
        try:
            return int(float(cleaned))
        except ValueError:
            return 0


def main():
    print("데이터 로드 및 전처리 중...")
    df = pd.read_csv(ACCOMMODATION_CSV, encoding="utf-8-sig")

    print(f"원본 데이터 로드 완료: 총 {len(df)}개 숙소 레코드")

    print("DB 연결 및 테이블 생성 중...")
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    # 확장 기능 설치
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 기존 테이블 초기화 (_ko 반영)
    cur.execute("DROP TABLE IF EXISTS acc_review_embedding_ko;")
    cur.execute("DROP TABLE IF EXISTS accommodation_embedding_ko;")
    cur.execute("DROP TABLE IF EXISTS accommodation_review_ko;")
    cur.execute("DROP TABLE IF EXISTS accommodation_ko;")

    # 데이터베이스 스키마 정의
    cur.execute("""
        CREATE TABLE accommodation_ko (
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

    # 1:N 리뷰 테이블
    cur.execute("""
        CREATE TABLE accommodation_review_ko (
            id               SERIAL PRIMARY KEY,
            accommodation_id BIGINT,
            content          TEXT
        );
    """)

    # 벡터 테이블 정의
    cur.execute(f"""
        CREATE TABLE accommodation_embedding_ko (
            id               SERIAL PRIMARY KEY,
            accommodation_id BIGINT,
            content          TEXT,
            embedding        vector({EMBEDDING_DIM})
        );
    """)
    cur.execute(f"""
        CREATE TABLE acc_review_embedding_ko (
            id               SERIAL PRIMARY KEY,
            accommodation_id BIGINT,
            content          TEXT,
            embedding        vector({EMBEDDING_DIM})
        );
    """)
    conn.commit()
    print("테이블 생성 완료")

    # 1. 일반 숙소 테이블 적재를 위한 데이터 가공
    print("숙소 데이터 가공 및 적재 중...")
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
                parse_int_with_comma(row["리뷰 갯수"]),  # 콤마 제거 함수 적용
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
        cur, f"INSERT INTO accommodation_ko ({', '.join(acc_cols)}) VALUES %s", acc_rows
    )

    # 2. 가로로 나열된 리뷰를 세로행 데이터로 녹여내기(Melting) 및 적재
    print("리뷰 데이터 정규화 및 적재 중...")
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
        "INSERT INTO accommodation_review_ko (accommodation_id, content) VALUES %s",
        rev_rows,
    )
    conn.commit()
    print(
        f"일반 테이블 적재 완료: 숙소 {len(acc_rows)}건, 분리된 리뷰 총 {len(rev_rows)}건"
    )

    # 3. 숙박 시설 임베딩 생성 & 저장
    print(f"숙소 벡터 생성 ({len(df)}개)...")
    acc_ids = df["id"].tolist()
    acc_texts = [build_accommodation_content(row) for _, row in df.iterrows()]
    acc_vectors = embed_all(acc_texts)

    acc_data = [
        (aid, txt, vec) for aid, txt, vec in zip(acc_ids, acc_texts, acc_vectors)
    ]
    execute_values(
        cur,
        "INSERT INTO accommodation_embedding_ko (accommodation_id, content, embedding) VALUES %s",
        acc_data,
        template="(%s, %s, %s::vector)",
    )
    conn.commit()
    print("숙소 벡터 저장 완료")

    # 4. 분리 적재된 리뷰 테이블 기반 임베딩 생성 & 저장
    print(f"리뷰 벡터 생성 ({len(rev_rows)}개)...")
    rev_ids = [r[0] for r in rev_rows]
    rev_texts = [r[1] for r in rev_rows]
    rev_vectors = embed_all(rev_texts)

    rev_data = [
        (aid, txt, vec) for aid, txt, vec in zip(rev_ids, rev_texts, rev_vectors)
    ]
    execute_values(
        cur,
        "INSERT INTO acc_review_embedding_ko (accommodation_id, content, embedding) VALUES %s",
        rev_data,
        template="(%s, %s, %s::vector)",
    )
    conn.commit()
    print("리뷰 벡터 저장 완료")

    # 인덱스 생성 (_ko 반영)
    print("인덱스 생성 중...")
    cur.execute(
        "CREATE INDEX ON accommodation_embedding_ko USING hnsw (embedding vector_cosine_ops);"
    )
    cur.execute(
        "CREATE INDEX ON acc_review_embedding_ko USING hnsw (embedding vector_cosine_ops);"
    )
    cur.execute(
        "CREATE INDEX ON accommodation_ko USING gin (hotel_style gin_trgm_ops);"
    )
    cur.execute("CREATE INDEX ON accommodation_embedding_ko (accommodation_id);")
    cur.execute("CREATE INDEX ON acc_review_embedding_ko (accommodation_id);")
    cur.execute("CREATE INDEX ON accommodation_review_ko (accommodation_id);")
    conn.commit()
    print("인덱스 생성 완료")

    # 데이터 적재 최종 확인
    print("\n[적재 확인]")
    for tbl in [
        "accommodation_ko",
        "accommodation_review_ko",
        "accommodation_embedding_ko",
        "acc_review_embedding_ko",
    ]:
        cur.execute(f"SELECT COUNT(*) FROM {tbl};")
        print(f"- {tbl}: {cur.fetchone()[0]}행")

    cur.close()
    conn.close()
    print("\n완료! 데이터 타입 보완 및 벡터 적재가 최종 완료되었습니다.")


if __name__ == "__main__":
    main()
