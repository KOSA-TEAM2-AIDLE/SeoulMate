# Attraction SearchCandidate Response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DSPy가 선택한 관광 후보 최대 3개를 공용 `SearchCandidate` 형식으로 `DomainAgentDispatchResult.candidates`에 반환한다.

**Architecture:** 검색 서비스가 생성한 `SearchCandidate`를 파이프라인 결과에 보존하고, DSPy의 `place_id` 선택 순서로 원본 후보를 다시 매핑한다. 공용 응답은 기본 빈 목록을 제공해 다른 도메인의 호환성을 유지한다.

**Tech Stack:** Python 3.12, Pydantic 2, DSPy, unittest

## Global Constraints

- 기본 최종 추천 개수는 `3`이다.
- 추천 개수는 중앙 설정값 하나로 변경할 수 있어야 한다.
- `candidates`는 DSPy 선택 순서를 유지한 원본 `SearchCandidate`다.
- 기존 `DomainAgentDispatchResult` 필드는 제거하거나 이름을 변경하지 않는다.

---

### Task 1: 공용 응답과 파이프라인 계약 고정

**Files:**
- Modify: `backend/schemas/travel_query_api.py`
- Modify: `backend/domains/attraction/recommendation_pipeline.py`
- Test: `backend/tests/test_attraction_answer_generator.py`

**Interfaces:**
- Produces: `AttractionRecommendationResult(answer: AttractionAnswerResult, candidates: list[SearchCandidate])`
- Produces: `DomainAgentDispatchResult.candidates: list[SearchCandidate]`

- [x] 선택된 ID 순서로 `SearchCandidate`를 보존하는 실패 테스트를 작성한다.
- [x] `uv run python -m unittest tests.test_attraction_answer_generator -v`로 기대한 실패를 확인한다.
- [x] 파이프라인 결과 모델과 공용 `candidates` 필드를 구현한다.
- [x] 동일 테스트를 재실행해 통과를 확인한다.

### Task 2: 추천 개수 중앙화와 에이전트 응답 연결

**Files:**
- Modify: `backend/core/config.py`
- Modify: `backend/domains/attraction/answer_generator.py`
- Modify: `backend/domains/attraction/answer_models.py`
- Modify: `backend/domains/attraction/answer_validation.py`
- Modify: `backend/domains/attraction/agent.py`
- Test: `backend/tests/test_attraction_agent.py`
- Test: `backend/tests/test_attraction_answer_validation.py`

**Interfaces:**
- Consumes: `settings.attraction_recommendation_limit`
- Produces: `AttractionAgent.execute(...).candidates`

- [x] 최대 3개와 순서를 검증하는 실패 테스트를 작성한다.
- [x] 관련 테스트를 실행해 기대한 실패를 확인한다.
- [x] 설정값을 DSPy 선택, fallback, 결과 모델과 에이전트에 적용한다.
- [x] 관련 및 디스패처 회귀 테스트를 실행한다.

### Task 3: 전체 영향 검증

**Files:**
- Verify: `backend/tests/`

**Interfaces:**
- Consumes: 변경된 공용 응답과 관광 파이프라인

- [x] `uv run python -m unittest tests.test_attraction_agent tests.test_attraction_answer_generator tests.test_attraction_answer_validation tests.test_domain_agent_dispatcher tests.test_travel_query_api -v`를 실행한다.
- [x] `git diff --check`로 패치 형식을 검증한다.
