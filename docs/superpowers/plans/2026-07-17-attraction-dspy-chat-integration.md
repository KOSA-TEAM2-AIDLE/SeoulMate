# Attraction DSPy Chat Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/chat`의 공통 후보·응답 계약을 유지하면서 관광 Task의 최종 후보 선택과 답변 생성에만 DSPy artifact를 사용한다.

**Architecture:** `AttractionSearchService`와 혼잡도 재랭커가 검증된 `SearchCandidate` 최대 10개를 만든다. 새 `AttractionSelectionService`가 해당 후보를 기존 DSPy Generator에 전달해 ID·선정 이유·답변만 생성하며, 공통 Chat 계층은 검증된 선택 결과를 `Place`, `recommendList`, SSE로 변환한다. 다른 도메인은 기존 공통 GPT 선택 경로를 유지한다.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI SSE, DSPy, unittest

## Global Constraints

- `/chat`의 `meta → token → done` SSE 계약을 변경하지 않는다.
- `SearchCandidate`, `Place`, `FrontendResponse` 스키마를 변경하지 않는다.
- DSPy는 후보 ID, 선정 이유, 자연어 답변만 생성한다.
- 장소명·주소·좌표·평점·리뷰 수·카테고리는 원본 후보에서만 복사한다.
- 관광 외 도메인은 기존 `generate_grouped_recommendation_result()` 경로를 유지한다.
- DSPy 장애·timeout·잘못된 ID는 `final_score` 순위 fallback으로 복구한다.
- 운영 요청에서는 최적화를 실행하지 않고 `optimized_program.json`만 로드한다.
- 한국어 질문은 한국어, 영어 질문은 영어로 답한다.

---

### Task 1: 관광 DSPy 선택 서비스 경계

**Files:**
- Create: `backend/application/recommendation/selection_models.py`
- Create: `backend/domains/attraction/selection_service.py`
- Test: `backend/tests/test_attraction_selection_service.py`

**Interfaces:**
- Consumes: `DomainSearchRequest`, `list[SearchCandidate]`, `AttractionAnswerGenerator.generate(...)`
- Produces: `CandidateSelectionResult(answer: str, selections: list[CandidateSelection])`

- [x] **Step 1: 선택 결과 계약과 DSPy 어댑터의 실패 테스트 작성**

  검증 항목은 요청 필드 전달, DSPy 선택 순서 보존, 원본 후보 밖 ID 차단이다.

- [x] **Step 2: 실패 테스트 실행**

  Run: `cd backend && uv run python -m unittest tests.test_attraction_selection_service -v`

  Expected: `selection_models` 또는 `selection_service`가 없어 FAIL.

- [x] **Step 3: 최소 선택 모델과 AttractionSelectionService 구현**

  `CandidateSelection`은 `place_id`, `selection_reason`만 허용하고 `CandidateSelectionResult`는 답변과 선택 목록을 반환한다. 서비스는 Generator가 검증한 결과를 공통 모델로 변환한다.

- [x] **Step 4: Step 1 테스트와 기존 DSPy 테스트 실행**

  Run: `cd backend && uv run python -m unittest tests.test_attraction_selection_service tests.test_attraction_answer_generator tests.test_attraction_answer_validation -v`

  Expected: 모두 PASS.

### Task 1.5: DSPy 입출력 null 문자열 정규화

**Files:**
- Create: `backend/domains/attraction/value_normalization.py`
- Modify: `backend/domains/attraction/answer_evidence.py`
- Modify: `backend/domains/attraction/answer_validation.py`
- Test: `backend/tests/test_attraction_answer_contract.py`
- Test: `backend/tests/test_attraction_answer_validation.py`

**Interfaces:**
- Consumes: DB·CSV·MCP에서 유입될 수 있는 `None`, 빈 문자열, `"null"`, `"none"`, `"nan"`, `"n/a"`, `"undefined"`
- Produces: 선택적 필드는 실제 `None`, 필수 필드와 DSPy 출력은 의미 있는 문자열만 허용

- [x] 입력 선택 필드의 문자열형 결측치를 `None`으로 바꾸는 실패 테스트를 작성한다.
- [x] 리뷰·혼잡도에 포함된 문자열형 결측치를 근거에서 제거하는 실패 테스트를 작성한다.
- [x] 필수 후보 필드와 DSPy 답변·선정 이유의 `"null"`을 거부하는 실패 테스트를 작성한다.
- [x] 공통 null 판별과 필드별 정규화를 구현한다.
- [x] 관련 DSPy 계약·Generator·선택 서비스 테스트를 통과시킨다.

### Task 2: 도메인 선택 전략 Registry

**Files:**
- Create: `backend/application/recommendation/selection_interface.py`
- Create: `backend/application/recommendation/selection_registry.py`
- Test: `backend/tests/test_selection_registry.py`

**Interfaces:**
- Consumes: `domain`, `DomainCandidateSelectionService`
- Produces: 관광에만 등록된 선택 서비스와 미등록 도메인 조회 결과

- [x] 관광만 전용 Selector로 등록되고 식당·카페·숙박은 기존 공통 GPT로 남는 실패 테스트를 작성한다.
- [x] Protocol과 Registry를 구현한다.
- [x] 중복 등록과 미등록 조회 계약을 검증한다.

### Task 3: 공통 그룹 선택 조정기

**Files:**
- Create: `backend/application/recommendation/group_selection.py`
- Test: `backend/tests/test_group_selection.py`

**Interfaces:**
- Consumes: 원본 Task 순서, Task별 `DomainSearchRequest`, 후보 wrapper, 전용 선택 Registry
- Produces: 현재 `generate_grouped_recommendation_result()`와 동일한 `answer`, `task_results` 구조

- [ ] 단일 관광 Task는 DSPy만 호출하는 실패 테스트를 작성한다.
- [ ] 관광이 없는 Task는 기존 공통 GPT를 한 번만 호출하는 테스트를 작성한다.
- [ ] 혼합 Task는 관광 DSPy 결과와 나머지 공통 GPT 결과를 원래 Task 순서로 병합하는 테스트를 작성한다.
- [ ] 전용 선택 결과의 ID를 wrapper 화이트리스트로 다시 검증하고 부족한 후보를 순위대로 보충한다.

### Task 4: `/chat` 실행 경로 연결

**Files:**
- Modify: `backend/routers/chat.py`
- Test: `backend/tests/test_domain_executor.py`
- Test: `backend/tests/test_mock_domain_agents.py`

**Interfaces:**
- Consumes: Task별 상위 10개 `SearchCandidate`, 관광 혼잡도 재랭킹 결과, 그룹 선택 조정기
- Produces: 기존 `Place`, `recommendList`, `meta → token → done`

- [ ] 관광 단일 추천에서 공통 GPT가 아니라 DSPy Selector가 호출되는 실패 테스트를 작성한다.
- [ ] 기존 후보 wrapper에 Task 요청을 보존하고 그룹 선택 조정기를 호출한다.
- [ ] 카페·숙박·식당 경로가 기존 선택기를 유지하는 회귀 테스트를 실행한다.
- [ ] 관광 응답의 `source_id`, 좌표, 주소, 카테고리가 원본 `SearchCandidate`와 일치하는지 검증한다.

### Task 5: 기존 AttractionAgent 중복 경로 축소

**Files:**
- Modify: `backend/domains/attraction/recommendation_pipeline.py`
- Modify: `backend/domains/attraction/agent.py`
- Test: `backend/tests/test_attraction_agent.py`
- Test: `backend/tests/test_attraction_answer_generator.py`

**Interfaces:**
- Consumes: 공통 AttractionSelectionService
- Produces: `/travel-query` Dispatcher에서도 `/chat`과 동일한 DSPy 선택 규칙

- [ ] Pipeline이 새 선택 서비스를 재사용하는 실패 테스트를 작성한다.
- [ ] 기존 `AttractionAnswerGenerator` 직접 호출을 선택 서비스로 교체한다.
- [ ] 위치·혼잡도·후보 개수 정책의 기존 테스트를 통과시킨다.

### Task 6: 전체 계약 및 실제 요청 검증

**Files:**
- Verify: `backend/tests/`

**Interfaces:**
- Consumes: 완성된 `/chat` 관광 DSPy 경로
- Produces: 팀 병합 가능한 검증 결과와 실행 명령

- [ ] Backend 전체 unittest를 실행한다.
- [ ] Weather MCP와 Restaurant 관련 테스트를 별도로 확인한다.
- [ ] `git diff --check`를 실행한다.
- [ ] 로컬 Vector DB와 Congestion MCP 환경에서 관광 질문의 SSE 결과를 확인한다.
- [ ] `meta.result.recommendList` 최대 3개와 token 답변 언어를 확인한다.
