# 관광지·행사 Vector DB 적재

`raw/`의 Visit Seoul 원본과 Google Maps 리뷰를 정제해 언어별
원본·리뷰·임베딩 테이블에 적재합니다.

행사 종료일이 기준일보다 이전이면 제외합니다. 종료일이 비어 있는 행사는 상시 행사 후보로
포함하며, 날짜 형식이 올바르지 않은 종료일은 `events_quarantine.csv`에 기록합니다.
상시 관광지는 포함합니다. 원본의 이미지 URL과 리뷰 기반 평점·리뷰 수를
장소 테이블에 함께 저장합니다.

## 테이블

```text
attraction_ko / attraction_en
attraction_review_ko / attraction_review_en
attraction_embedding_ko / attraction_embedding_en
attraction_review_embedding_ko / attraction_review_embedding_en
```

## 실행

DB와 OpenAI API를 호출하지 않고 정제 건수만 확인합니다.

```bash
uv run python -m vector_db.attraction.seed_vectordb \
  --dry-run \
  --as-of 2026-07-17
```

기존 관광 테이블을 삭제하고 전체 데이터를 재적재합니다. 삭제부터 신규
인덱스 생성까지 하나의 DB 트랜잭션으로 실행되므로 실패하면 롤백됩니다.

```bash
uv run python -m vector_db.attraction.seed_vectordb \
  --rebuild \
  --as-of 2026-07-17 \
  --batch-size 200
```

임베딩 모델과 차원은 `core.config`의 `OPENAI_EMBED_MODEL`,
`OPENAI_EMBED_DIM`을 사용합니다.
