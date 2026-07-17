# 관광 검색 신규 DB 전환 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 삭제된 단일 Vector Document 검색을 언어별 관광 원본·장소 임베딩·리뷰 임베딩 검색으로 교체한다.

**Architecture:** 카페 도메인과 동일하게 Repository는 DB 조회, Reranker는 필터·점수, Mapper는 `SearchCandidate` 변환, SearchService는 조정만 담당한다. 제외 조건은 임베딩 문장에서 제거하고 재랭킹 전 하드 필터로 적용한다.

**Tech Stack:** Python 3.12, psycopg2, pgvector cosine search, OpenAI embedding, Pydantic `SearchCandidate`

## Global Constraints

- 새 테스트 파일은 작성하지 않는다.
- 커밋은 수행하지 않는다.
- 공통 `DomainSearchRequest`, `SearchCandidate`의 스키마를 변경하지 않는다.
- 좌표 없는 후보는 위치 반경·혼잡도 요청에서 제외한다.
- 종료 행사는 조회하지 않는다.

## Task 1: Repository 교체

**Files:**
- Replace: `backend/domains/attraction/repository.py`

**Produces:** `AttractionRecord`, `AttractionVectorHit`, `ReviewVectorHit`, `AttractionRetrievalResult`, `AttractionRepository.retrieve()`

- [x] 언어별 테이블 이름을 선택한다.
- [x] 질문을 한 번 임베딩한다.
- [x] 장소 임베딩 상위 300개와 전역 리뷰 풀 200개를 조회한다.
- [x] Vector ID의 원본 장소를 조회해 이미지·평점·리뷰 수를 복원한다.
- [x] 최종 후보별 근거 리뷰 5건을 다시 조회한다.

## Task 2: Reranker·Mapper 구현

**Files:**
- Replace: `backend/domains/attraction/reranker.py`
- Replace: `backend/domains/attraction/mapper.py`

**Produces:** `AttractionReranker.rerank()`, `to_search_candidate()`

- [x] 종료 행사, 명시적 카테고리, 제외 조건, 반경, 최소 평점을 필터링한다.
- [x] 장소·리뷰 RRF와 카테고리 boost를 결합한다.
- [x] 원본 이미지·평점·리뷰 수·URL·운영시간을 `attributes`에 넣는다.
- [x] Vector·리뷰·카테고리·거리 점수를 `signals`에 넣는다.

## Task 3: SearchService 연결

**Files:**
- Replace: `backend/domains/attraction/search_service.py`
- Modify: `backend/domains/attraction/search_plan.py`

- [x] 기준 위치와 일반 관광 도메인명을 제거한 의미 검색어를 만든다.
- [x] `excluded_features`를 의미 검색어에 넣지 않는다.
- [x] Repository → Reranker → 근거 리뷰 → Mapper 순서로 실행한다.

## Task 4: 실제 질문 검증

- [x] `종로에서 궁궐 추천`의 Vector/RRF 후보를 확인한다.
- [x] `남산타워 근처 고궁`의 카테고리·거리 필터를 확인한다.
- [x] 후보의 `image`, `rating`, `review_count`가 `SearchCandidate.attributes`에 있는지 확인한다.
- [x] 운영 검색 Repository의 기존 테이블 참조가 제거됐음을 확인한다.
