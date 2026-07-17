# 관광·행사 데이터 파이프라인 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 카페 도메인과 같은 언어별 원본·장소 임베딩·리뷰·리뷰 임베딩 테이블에 관광지·활성 행사·리뷰를 손실 없이 적재한다.

**Architecture:** `vector_db.attraction.seed_vectordb`를 단일 CLI 진입점으로 사용한다. 전처리는 `scripts.data_pipeline.attraction`의 작은 모듈에서 수행하고, 적재기는 기존 단일 Vector 테이블을 제거한 뒤 원본·리뷰·임베딩을 언어별로 생성한다. 전체 과정은 하나의 DB 트랜잭션으로 실행한다.

**Tech Stack:** Python 3.12, uv, csv, dataclasses, psycopg2, PostgreSQL 16, pgvector, OpenAI `text-embedding-3-large` 1536차원

## Global Constraints

- 신규 테스트 파일을 작성하지 않는다.
- 새 스크립트는 `--dry-run`으로 API·DB 쓰기 없이 검증할 수 있어야 한다.
- `--rebuild`는 기존 `attraction_vector_documents`를 삭제하고 신규 구조로 전체 적재한다.
- 행사 종료일이 기준일보다 이전이면 제외한다.
- 행사 종료일이 없으면 유지한다.
- `main_image_url`, `avg_rating`, `review_count`를 원본 테이블에 보존한다.
- 한·영 장소는 `place_key`로 논리적으로 연결하되 언어별 테이블에 독립 저장한다.
- 커밋은 수행하지 않는다.

---

## 파일 구조

- Create: `backend/vector_db/attraction/seed_vectordb.py`  
  CLI, 스키마 생성, 원본 upsert, 임베딩 upsert, 인덱스 생성을 조정한다.
- Create: `backend/scripts/data_pipeline/attraction/dataset.py`  
  원천 CSV와 리뷰 CSV를 한·영 `CleanedAttractionDataset`으로 조립한다.
- Modify: `backend/scripts/data_pipeline/attraction/models.py`  
  이미지·평점·리뷰 집계를 포함하는 불변 데이터 계약을 추가한다.
- Modify: `backend/scripts/data_pipeline/attraction/transform.py`  
  `main_image_url`을 보존하고 현재 행사 필터 규칙을 유지한다.
- Modify: `backend/scripts/data_pipeline/attraction/reviews.py`  
  장소별 평균 평점·리뷰 수·언어 통계를 적재 모델로 전달한다.
- Modify: `backend/data/attraction/README.md`  
  `--dry-run`, `--rebuild`, 일반 upsert 실행법과 테이블 구조를 기록한다.

## Task 1: 원천 데이터 계약 확정

**Files:**
- Modify: `backend/scripts/data_pipeline/attraction/models.py`
- Create: `backend/scripts/data_pipeline/attraction/dataset.py`

**Interfaces:**
- Consumes: Visit Seoul CSV `dict[str, str]`, Google review CSV `dict[str, str]`, `as_of: date`
- Produces: `clean_attraction_datasets(data_dir: Path, as_of: date) -> tuple[CleanedAttractionDataset, ...]`

- [x] **Step 1: 원본 컬럼을 읽기 전용 명령으로 대조한다.**

  Run:
  ```bash
  cd backend
  head -1 data/attraction/raw/visit_seoul_master_ko_no_food_accommodation.csv
  head -1 data/attraction/raw/visit_seoul_master_en_no_food_accommodation.csv
  head -1 data/attraction/raw/reviews/google_maps_reviews_raw_by_category_top100_refined.csv
  ```

  Expected: 장소에 `cid`, `lang_code_id`, `category_path`, `name`, `description_text`, `main_image_url`, 리뷰에 `place_key`, `review_id`, `rating`, `original_text`가 있다.

- [x] **Step 2: 데이터 계약을 추가한다.**

  `AttractionPlaceRecord`, `AttractionReviewRecord`, `AttractionCleaningReport`, `CleanedAttractionDataset`을 불변 dataclass로 정의한다. `AttractionPlaceRecord.embedding_content`는 `Name`, `Kind`, `Category`, `Summary`, `Description`, `Tags`, `Address`, `Hours`, `Fee`, `Event period`만 포함한다.

- [x] **Step 3: 정제 함수를 구현한다.**

  `clean_attraction_datasets()`는 언어별 장소와 리뷰를 만들고, orphan·빈 리뷰·잘못된 날짜·종료 행사 건수를 report에 기록한다.

- [x] **Step 4: 쓰기 없이 직접 호출해 검증한다.**

  Run:
  ```bash
  cd backend
  PYTHONDONTWRITEBYTECODE=1 uv run python -c "from datetime import date; from pathlib import Path; from scripts.data_pipeline.attraction.dataset import clean_attraction_datasets; d=clean_attraction_datasets(Path('data/attraction'), date.today()); [print(x.language, len(x.places), len(x.reviews), x.report) for x in d]"
  ```

  Expected: `ko`, `en` 두 dataset이 생성되고 장소·리뷰·제외 건수가 양수로 출력된다.

## Task 2: 언어별 스키마와 `--dry-run`

**Files:**
- Create: `backend/vector_db/attraction/seed_vectordb.py`

**Interfaces:**
- Consumes: `tuple[CleanedAttractionDataset, ...]`
- Produces: `_table_names(language)`, `create_schema(cursor, language, rebuild)`, CLI `main()`

- [x] **Step 1: 언어별 테이블 이름을 정의한다.**

  `_table_names('ko')`는 `attraction_ko`, `attraction_review_ko`, `attraction_embedding_ko`, `attraction_review_embedding_ko`를 반환하고, `en`도 동일하게 작동한다.

- [x] **Step 2: 원본·리뷰·임베딩 테이블 DDL을 구현한다.**

  장소 테이블은 `id TEXT PRIMARY KEY`를 사용하고, 리뷰는 `(source_review_id, attraction_id)` 유니크 제약과 외래 키를 사용한다. 두 임베딩 컬럼은 `vector(1536)`으로 생성한다.

- [x] **Step 3: CLI에 `--dry-run`, `--rebuild`, `--as-of`, `--batch-size`를 추가한다.**

  `--dry-run`은 `clean_attraction_datasets()`와 report 출력만 수행하고 DB 연결과 OpenAI 호출을 하지 않는다.

- [x] **Step 4: dry-run을 실행한다.**

  Run:
  ```bash
  cd backend
  uv run python -m vector_db.attraction.seed_vectordb --dry-run --as-of 2026-07-17
  ```

  Expected: 언어별 장소·활성 행사·리뷰·격리 통계가 출력되고 DB 테이블은 변하지 않는다.

## Task 3: 원본 테이블 적재

**Files:**
- Modify: `backend/vector_db/attraction/seed_vectordb.py`

**Interfaces:**
- Consumes: `CleanedAttractionDataset`
- Produces: `upsert_base_data(cursor, dataset) -> dict[tuple[str, str], int]`

- [x] **Step 1: 장소 upsert를 구현한다.**

  `ON CONFLICT (id) DO UPDATE`로 이미지, 평점, 리뷰 수, 설명, 좌표, 행사 날짜를 포함한 모든 표시용 필드를 갱신한다.

- [x] **Step 2: 리뷰 upsert를 구현한다.**

  orphan 리뷰는 이미 정제 단계에서 제외되므로, 적재 단계에서는 외래 키 위반을 오류로 처리한다.

- [x] **Step 3: 원본 적재 건수를 임베딩 적재 건수와 대조한다.**

  Expected: dataset의 장소·리뷰 건수와 DB의 언어별 건수가 일치한다. 트랜잭션 중 오류가 나면 해당 언어 적재를 롤백한다.

## Task 4: 장소·리뷰 임베딩 적재

**Files:**
- Modify: `backend/vector_db/attraction/seed_vectordb.py`

**Interfaces:**
- Consumes: `Sequence[str]`, `OPENAI_EMBED_MODEL`, `OPENAI_EMBED_DIM`
- Produces: `EmbeddingClient.embed(texts: Sequence[str]) -> list[list[float]]`, `upsert_embeddings(...) -> None`

- [x] **Step 1: 카페와 동일한 배치 임베딩 Client를 구현한다.**

  응답 백터 개수가 입력 문장 개수와 다르면 적재하지 않고 `RuntimeError`를 발생시킨다.

- [x] **Step 2: 장소 임베딩 upsert를 구현한다.**

  `attraction_embedding_{lang}`에 `attraction_id`, `content`, `content_hash`, `embedding`을 저장하고 해시가 동일하면 API 호출을 건너뛴다.

- [x] **Step 3: 리뷰 임베딩 upsert를 구현한다.**

  `attraction_review_embedding_{lang}`은 리뷰 PK, 장소 ID, 문장, 해시, 백터를 저장한다.

- [x] **Step 4: HNSW와 외래 키 조회 인덱스를 생성한다.**

  장소·리뷰 임베딩에 `vector_cosine_ops` HNSW, 카테고리에 trigram GIN, 리뷰의 `attraction_id`에 B-tree 인덱스를 생성한다.

## Task 5: 전체 적재와 무결성 확인

**Files:**
- Modify: `backend/data/attraction/README.md`

**Interfaces:**
- Consumes: 완성된 `seed_vectordb` CLI
- Produces: 언어별 4계층 신규 테이블

- [x] **Step 1: dry-run 최종 통계를 기록한다.**

  Run:
  ```bash
  cd backend
  uv run python -m vector_db.attraction.seed_vectordb --dry-run --as-of 2026-07-17
  ```

- [x] **Step 2: 전체 임베딩 대상 건수를 확인한다.**

  사용자가 승인한 모델 `text-embedding-3-large`, 1536차원과 장소·리뷰 전체 문서 건수를 출력한다.

- [x] **Step 3: 신규 테이블을 전체 재구축한다.**

  Run:
  ```bash
  cd backend
  uv run python -m vector_db.attraction.seed_vectordb --rebuild --as-of 2026-07-17
  ```

  Expected: 언어별 장소·리뷰·장소 임베딩·리뷰 임베딩 건수가 일치한다.

- [x] **Step 4: SQL 읽기 조회로 표시용 필드를 확인한다.**

  한글 남산서울타워·덕수궁·현재 행사 표본을 조회하여 `image`, `rating`, `review_count`, `latitude`, `longitude`, `category`, `kind`가 원본과 일치하는지 확인한다.

- [x] **Step 5: README에 실행법과 로그 해석법을 기록한다.**

## 완료 기준

- `--dry-run`이 DB·OpenAI 호출 없이 성공한다.
- 종료 행사는 신규 장소 테이블에 없다.
- 종료일이 없는 행사는 유지된다.
- 모든 임베딩은 존재하는 원본 장소 또는 리뷰를 참조한다.
- 장소 표본의 이미지·평점·리뷰 수·좌표가 DB에 있다.
- 기존 `attraction_vector_documents`는 제거되고 언어별 신규 테이블로 대체된다.
