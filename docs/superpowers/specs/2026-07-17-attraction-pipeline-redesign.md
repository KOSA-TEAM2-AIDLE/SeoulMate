# 관광·행사 데이터 파이프라인과 추천 구조 재설계

## 1. 목적

관광·행사 도메인을 현재 정상 동작하는 카페 도메인과 동일한 기본 구조로 재정렬한다. 원천 데이터 전처리부터 Vector DB 적재, 검색, 재랭킹, MCP 컨텍스트, DSPy 선택, 프론트엔드 응답까지의 단일한 실행 경로를 만든다.

핵심 목표는 다음과 같다.

- 원본의 이미지·평점·리뷰 수·좌표를 응답까지 손실 없이 전달한다.
- `남산타워 주변 고궁`에서 기준 위치와 검색 대상을 분리한다.
- 제외 조건을 임베딩의 긍정 검색어로 사용하지 않는다.
- 조건을 만족하는 후보가 없으면 무관한 후보를 채우지 않는다.
- 날씨와 혼잡도는 공통 Context Provider 계약으로 연결하고, 도메인별 재랭커가 점수 반영을 책임진다.
- DSPy는 관광·행사의 최종 선택과 답변 생성에만 사용한다.

## 2. 현재 상태와 문제

현재 DB에는 `attraction_vector_documents` 11,149건이 있다. 화면에 이미지와 평점이 나오지 않는 주요 원인은 미적재가 아니라 Document 메타데이터 생성 시 `main_image_url`, `avg_rating`, `review_count`를 버린 것이다.

구조적 문제는 다음과 같다.

1. 카페는 원본·임베딩·리뷰·리뷰 임베딩 테이블을 분리하지만, 관광은 모든 Document를 하나의 테이블에 저장한다.
2. 관광 검색 후보는 원본 테이블을 다시 조회하지 않아 표시용 필드를 복원할 수 없다.
3. 제외 조건이 검색 임베딩 문장에 포함되어 제외할 대상의 유사도가 높아질 수 있다.
4. `/chat`은 `AttractionAgent.execute()`를 호출하지 않고 `AttractionSearchService`를 직접 호출한다. Agent와 실제 채팅 경로가 이중화되어 있다.
5. 관광 혼잡도는 날씨용 `rag_mcp` 모드에 묶여 있다.
6. DSPy 검증과 그룹 선택 보정이 선택 개수를 강제하여, 0개가 올바른 제약 질문에서도 무관한 후보가 추가된다.

## 3. 목표 아키텍처

### 3.1 단일 실행 경로

```text
/chat
→ TravelQueryStartRequest
→ StructuredTravelQuery
→ 위치·검색 대상·제외 조건 분리
→ DomainSearchRequest
→ AttractionSearchService
→ AttractionRepository
→ AttractionReranker
→ 날씨·혼잡도 Context
→ AttractionSelectionService(DSPy)
→ SearchCandidate
→ Place
→ 프론트엔드 recommendation
```

`AttractionAgent`는 위 공통 실행 경로를 호출하는 얇은 어댑터로 만든다. 위치 해석, MCP 선택, DSPy 선택을 Agent와 `/chat`에 중복 구현하지 않는다.

### 3.2 테이블

```text
attraction_ko / attraction_en
attraction_embedding_ko / attraction_embedding_en
attraction_review_ko / attraction_review_en
attraction_review_embedding_ko / attraction_review_embedding_en
```

관광지와 행사는 같은 원본 테이블에 저장하고 `kind=attraction|event`로 구분한다. 리뷰는 원본 테이블의 외래 키로 장소와 연결한다.

`--rebuild`에서 기존 `attraction_vector_documents`를 제거하고 언어별 신규 구조로 전체 재적재한다. 삭제와 신규 적재는 하나의 DB 트랜잭션에서 실행하여 실패 시 모두 롤백한다.

### 3.3 원본 장소 계약

- `id`, `source_cid`, `language`, `kind`
- `name`, `category`, `category_primary`, `category_secondary`
- `summary`, `description`, `tags`
- `address`, `latitude`, `longitude`
- `hours`, `fee`, `image`, `link`
- `start_date`, `end_date`
- `rating`, `review_count`
- `english_review_count`, `foreign_review_count`

프론트엔드 표시용 필드는 Vector Document를 파싱하지 않고 원본 테이블에서 조회한다.

## 4. 전처리와 적재

### 4.1 규칙

1. CSV 필수 컬럼과 중복 ID를 검증한다.
2. `description_text`를 설명으로 사용하되, 빈 값은 요약으로 보완한다.
3. 좌표·날짜·평점을 정규화하고 유효하지 않은 필수값은 격리한다.
4. 행사 종료일이 기준일보다 이전이면 제외한다.
5. 행사 종료일이 없으면 상시 운영 가능성이 있으므로 유지한다.
6. 리뷰는 활성 장소 ID에 연결되는 항목만 유지한다.
7. 리뷰의 평점으로 장소별 평균 평점과 리뷰 수를 산출한다.

### 4.2 Document

장소 임베딩 Document는 `Name`, `Kind`, `Category`, `Summary`, `Description`, `Tags`, `Address`, `Hours`, `Fee`, `Event period`로 구성한다. 이미지, 평점, 리뷰 수, 좌표, 홈페이지는 원본 테이블에서 관리한다. 리뷰는 각각 독립적으로 임베딩한다.

### 4.3 실행 인터페이스

```bash
uv run python -m vector_db.attraction.seed_vectordb --dry-run
uv run python -m vector_db.attraction.seed_vectordb --rebuild
uv run python -m vector_db.attraction.seed_vectordb
```

- `--dry-run`: 정제·연결·제외 통계만 출력한다.
- `--rebuild`: 신규 관광 테이블을 재생성하고 전체 적재한다.
- 옵션 없음: ID 기준 upsert와 해시 비교로 변경 데이터를 반영한다.

## 5. 검색과 재랭킹

### 5.1 역할

- `AttractionRepository`: 질문 임베딩, 장소·리뷰 Vector 조회, 원본 장소 조회만 담당한다.
- `AttractionReranker`: 명시적 필터와 점수 결합을 담당한다.
- `AttractionMapper`: 재랭킹 결과를 공통 `SearchCandidate`로 변환한다.
- `AttractionSearchService`: 위 과정을 순서대로 조정한다.

### 5.2 질문 정규화

`남산타워 주변에 외국인이 갈만한 고궁`은 `기준 위치=남산타워`, `검색 대상=고궁`, `테마=외국인`으로 분리한다. 기준 위치와 `근처`, `주변` 등의 일반 표현은 의미 임베딩 질문에서 제거한다.

`excluded_features`는 임베딩 문장에 포함하지 않는다. 이름·카테고리·설명·태그·리뷰 근거에서 제외 조건이 확인되면 후보를 제거한다.

### 5.3 점수

하드 제약을 먼저 적용한 후 다음 요소를 RRF로 결합한다.

- 장소 Document Vector 순위
- 리뷰 Vector 순위
- 명시적 카테고리 일치
- 필수·제외 조건
- 기준 위치와의 거리
- 최소 평점
- 행사 진행 상태

운영 가중치는 실제 질문 결과 비교 후 상수 또는 설정으로 고정한다.

## 6. 날씨와 혼잡도

날씨와 혼잡도는 공통 Context Provider로 제공한다. MCP 실패 시 정적 검색 결과는 유지한다.

- 날씨는 방문일·시간 또는 날씨 조건이 있을 때 조회하고, 실내·실외 적합성을 관광 정책으로 반영한다.
- 혼잡도는 위치가 확인된 관광 후보의 좌표를 기준으로 조회한다.
- `한적한`, `덜 붐비는`과 같은 명시적 요청에서만 혼잡도 가중치를 크게 적용한다.
- 관측값이 없거나 오래되면 혼잡 상태를 추론하지 않는다.
- 현재의 날씨용 `rag_mcp` 분기와 관광 혼잡도 호출 여부를 분리한다.

## 7. DSPy 경계

DSPy는 정적 필터와 재랭킹을 통과한 상위 후보만 받는다.

- 후보 ID, 근거 기반 선정 이유, 최종 답변만 생성한다.
- 후보에 없는 장소나 사실을 생성하지 않는다.
- 0개부터 `ATTRACTION_RECOMMENDATION_LIMIT`까지 선택할 수 있다.
- 조건을 만족하는 후보가 없으면 `적합한 후보 없음`을 정상 결과로 반환한다.
- 한글 질문은 한글, 영어 질문은 영어로 답변한다.
- 혼잡도·날씨 근거가 없으면 관련 상태를 추론하지 않는다.
- 공통 그룹 보정은 의도적인 0개 결과를 다른 후보로 채우지 않는다.

## 8. 오류 처리

- 원본 오류: 행 단위 격리와 사유별 통계를 남긴다.
- 임베딩 API 오류: 해당 배치를 롤백하고 실패를 명시한다.
- 위치 해석 실패: 명시적 반경을 요청했다면 오류를 반환하고, 그렇지 않으면 거리 필터 없이 검색한다.
- MCP 실패: 정적 검색 결과를 유지하고 실패 신호를 `signals`에 남긴다.
- DSPy 출력 오류: 후보 ID와 근거를 검증한 뒤 안전한 정적 답변으로 전환한다.
- 빈 후보: 실패로 간주하지 않고 조건에 맞는 장소가 없다는 정상 응답을 생성한다.

## 9. 검증

새 테스트 파일은 작성하지 않는다. 다음 실행 결과로 단계별 경계를 확인한다.

1. `--dry-run` 정제 통계와 격리 사유
2. 테이블별 적재 건수와 원본 대조
3. 임베딩과 원본 장소의 ID 참조 무결성
4. `AttractionSearchService` 직접 호출의 필터 전·후 후보
5. 날씨·혼잡도 MCP 실제 응답과 실패 fallback
6. `/travel-query/start`의 구조화 결과
7. `/chat` SSE의 후보·선정 이유·이미지·평점

필수 회귀 질문은 다음과 같다.

- `남산타워 주변에 외국인이 갈만한 고궁을 추천해줘`
- `IT벤처타워 근처에서 아이와 체험하려고 해. 물과 실탄사격을 제외해줘`
- `오늘 고즈넉한 관광지를 추천해줘`
- `Recommend palaces near Namsan Tower for foreign visitors.`

## 10. 단계적 전환

1. 원천 컬럼·리뷰 연결 계약을 확정한다.
2. 신규 전처리기와 언어별 4계층 테이블을 구축한다.
3. 전체 데이터를 신규 테이블에 적재한다.
4. 카페 패턴의 Repository·Reranker·Mapper로 관광 검색을 교체한다.
5. 위치 해석과 제외 조건을 정상화한다.
6. 날씨·혼잡도 정책을 공통 Orchestrator 경로에 연결한다.
7. DSPy 검증과 0개 선택 계약을 수정한다.
8. 실제 API 질문으로 신·구 결과를 비교한다.
9. 신규 Repository와 검색 경로를 언어별 테이블에 연결한다.

## 11. 비목표

- 식당·카페·숙소의 도메인 재랭킹 정책은 변경하지 않는다.
- 모든 도메인에 DSPy를 도입하지 않는다.
- 날씨·혼잡도 MCP 서버의 외부 API 구현을 교체하지 않는다.
- 기존 단일 Vector 테이블은 전체 재적재 트랜잭션에서 신규 구조로 대체한다.
