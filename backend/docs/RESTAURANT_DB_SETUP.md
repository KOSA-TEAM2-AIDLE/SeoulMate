# 식당 RAG DB 원클릭 구축 가이드

이 가이드는 팀원이 별도 SQL이나 노트북을 실행하지 않고, 저장소의 CSV 6개로 식당 검색 DB를 동일하게 만드는 방법을 설명합니다.

## 결과물

한 번 실행하면 다음 작업이 순서대로 수행됩니다.

1. CSV 6개 헤더·중복 ID·외래키·좌표·평점 검증
2. 식당 도메인 테이블 12개만 초기화
3. `pgvector`, `pg_trgm` 확장과 테이블 생성
4. 한글/영문 식당·메뉴·리뷰 CSV 적재
5. OpenAI 임베딩 생성
6. cosine HNSW 인덱스 생성
7. CSV 행 수, 임베딩 행 수, 벡터 1536차원 검증

카페·숙박·명소·물품보관소 등 다른 도메인 테이블은 삭제하지 않습니다.

## 최초 1회 준비

### 1. PostgreSQL 준비

- PostgreSQL에 `pgvector` 확장이 설치되어 있어야 합니다.
- 기본 프로젝트 연결값은 `localhost:5433`, DB 이름 `seoulmate`입니다.
- 지정한 DB가 없고 DB 계정에 `CREATEDB` 권한이 있으면 스크립트가 자동 생성합니다.

### 2. 환경변수 준비

`backend/.env.example`을 `backend/.env`로 복사한 뒤 다음 값을 입력합니다.

```dotenv
DB_HOST=localhost
DB_PORT=5433
DB_NAME=seoulmate
DB_USER=seoulmate
DB_PASSWORD=실제비밀번호

OPENAI_API_KEY=실제키
OPENAI_EMBED_MODEL=text-embedding-3-large
OPENAI_EMBED_DIM=1536
```

API 키는 Git에 커밋하거나 팀 채팅에 올리지 않습니다.

## 실행 방법

저장소의 `backend` 폴더에서 다음 한 줄만 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_restaurant_db.ps1
```

기본 실행은 기존 **식당 관련 테이블만** 초기화한 뒤 완전히 다시 만듭니다. 임베딩 약 4만 6천 건을 API로 생성하므로 네트워크와 API 비용이 발생하며 시간이 걸릴 수 있습니다.

## 중단 후 이어서 실행

중간에 터미널이 종료되거나 API 오류가 발생한 경우, 완료된 임베딩을 다시 결제하지 않도록 다음처럼 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_restaurant_db.ps1 -Resume
```

이미 같은 모델·같은 본문으로 생성된 임베딩은 건너뜁니다.

## 검증만 실행

CSV 파일만 검사하며 DB와 OpenAI API를 사용하지 않습니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_restaurant_db.ps1 -ValidateOnly
```

현재 DB가 CSV 및 임베딩과 일치하는지만 검사합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_restaurant_db.ps1 -VerifyOnly
```

## CSV만 먼저 적재

OpenAI 키 없이 테이블과 원본 데이터만 확인할 때 사용합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_restaurant_db.ps1 -SkipEmbeddings
```

이 상태에서는 벡터 RAG 검색이 동작하지 않습니다. 이후 `.env`에 키를 넣고 `-Resume`으로 임베딩을 완성해야 합니다.

## 생성되는 테이블

| 구분 | 한글 | 영어 |
|---|---|---|
| 식당 | `restaurant_ko` | `restaurant_en` |
| 메뉴 | `restaurant_menu_ko` | `restaurant_menu_en` |
| 리뷰 | `restaurant_review_ko` | `restaurant_review_en` |
| 식당 벡터 | `restaurant_embedding_ko` | `restaurant_embedding_en` |
| 메뉴 벡터 | `menu_embedding_ko` | `menu_embedding_en` |
| 리뷰 벡터 | `review_embedding_ko` | `review_embedding_en` |

## 정상 완료 기준

마지막에 `[DONE] 식당 DB 구축 및 검증 완료`가 출력되어야 합니다. 원본 건수는 다음과 같습니다.

- 식당: 한글 1,000 / 영어 1,000
- 메뉴: 한글 10,003 / 영어 9,697
- 리뷰: 한글 14,996 / 영어 9,745
- 각 임베딩 테이블: 대응 원본 테이블과 동일한 행 수
- 모든 벡터: 1536차원

영어 메뉴가 한글보다 306개 적은 것은 오류가 아닙니다. 영어 식당 원본이 없는 메뉴를 외래키 무결성을 위해 제외한 결과입니다.

## 주요 파일 역할

- `data/db_seed/restaurant/*.csv`: DB 원본 데이터 6개
- `vector_db/restaurant/schema.sql`: 테이블·제약조건·일반 인덱스
- `scripts/setup_restaurant_db.py`: 검증·적재·임베딩·HNSW·최종 검증
- `scripts/setup_restaurant_db.ps1`: 팀원이 실행하는 진입점
- `tests/test_setup_restaurant_db.py`: 시드 회귀 테스트

기존 `build_vectordb_L3.ipynb`는 과거 실험 기록입니다. 재현 가능한 팀 공용 DB 구축에는 사용하지 않습니다.
