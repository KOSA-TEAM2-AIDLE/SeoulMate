# Attraction Initial Query Congestion MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 최초 관광 질문의 위치 의도를 해석하고 Vector DB 후보에 혼잡도 MCP를 선택적으로 적용한 뒤 DSPy 최종 후보를 반환한다.

**Architecture:** `TravelQueryStartRequest`의 현재 좌표를 외부 JSON에 노출하지 않는 실행 컨텍스트로 응답에 보존한다. `AttractionAgent`가 현재 위치 표현은 사용자 좌표로, 시설명은 `SearchLocationResolver`로 해석하며, 지역 앵커가 있거나 혼잡도 선호가 명시된 최초 질문에만 상위 후보별 MCP를 적용한다.

**Tech Stack:** Python 3.12, Pydantic 2, MCP, Kakao Local, DSPy, unittest

## Global Constraints

- `/chat` 및 후속 질문 상태 저장은 수정하지 않는다.
- `TravelQueryApiResponse`의 외부 JSON 구조는 변경하지 않는다.
- MCP 실패는 추천 전체를 실패시키지 않고 기존 `final_score`를 유지한다.
- 광범위 일반 질문은 MCP를 생략하고, 광범위여도 혼잡도 선호가 있으면 정적 후보 생성 후 MCP를 호출한다.
- DSPy 최종 후보는 `SearchCandidate` 형식과 중앙 추천 개수 설정을 유지한다.

---

### Task 1: 요청 실행 컨텍스트 보존

**Files:**
- Modify: `backend/schemas/travel_query_api.py`
- Modify: `backend/application/travel_query/service.py`
- Test: `backend/tests/test_travel_query_api.py`

- [x] 좌표가 외부 JSON에 노출되지 않으면서 디스패처에 전달되는 실패 테스트를 작성한다.
- [x] 테스트의 기대 실패를 확인한다.
- [x] 직렬화 제외 실행 컨텍스트를 구현한다.
- [x] 테스트 통과를 확인한다.

### Task 2: 위치 해석과 MCP 정책

**Files:**
- Modify: `backend/domains/attraction/agent.py`
- Modify: `backend/domains/attraction/congestion_reranker.py`
- Test: `backend/tests/test_attraction_agent.py`

- [x] 현재 위치, 시설명, 광범위 일반, 광범위 혼잡도 질문 정책 테스트를 작성한다.
- [x] 테스트의 기대 실패를 확인한다.
- [x] `SearchLocationResolver`와 혼잡도 선호 키워드 정책을 연결한다.
- [x] 정책 테스트 통과를 확인한다.

### Task 3: 기본 MCP 파이프라인 주입과 회귀 검증

**Files:**
- Modify: `backend/domains/attraction/recommendation_pipeline.py`
- Modify: `backend/domains/attraction/agent.py`
- Test: `backend/tests/test_attraction_answer_generator.py`
- Test: `backend/tests/test_attraction_congestion_reranker.py`

- [x] `use_congestion=False`에서 MCP 미호출, `True`에서 호출을 검증하는 실패 테스트를 작성한다.
- [x] `CongestionMCPProvider`와 `AttractionCongestionReranker`를 기본 관광 파이프라인에 주입한다.
- [x] 관련 테스트와 `/travel-query` 회귀 테스트를 실행한다.
- [x] `git diff --check`로 변경 형식을 검증했다.
