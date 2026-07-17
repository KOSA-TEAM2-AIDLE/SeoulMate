# 관광 추천 파이프라인 마무리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 관광 DSPy의 0개 선택, 날씨 Context, 실제 API 회귀 검증을 완성한다.

**Architecture:** `AttractionAgent`는 카페와 같이 Task 선택·`DomainSearchRequest` 생성·결과 반환만 담당한다. `AttractionSearchService`는 Repository·Reranker·Mapper까지만 수행하고, `AttractionContextEnricher`가 혼잡도·날씨 MCP와 도메인 점수를 담당한 후 DSPy Selector가 0개부터 설정 상한까지 선택한다.

**Tech Stack:** Python 3.12, Pydantic, DSPy, MCP ContextProvider

## Global Constraints

- 식당·카페·숙소 선택 정책은 변경하지 않는다.
- 날씨 근거가 없으면 실내·실외 적합성을 추론하지 않는다.
- 별도 테스트 파일과 Git 커밋을 만들지 않는다.

### Task 1: 0개 선택 계약

- Modify: `backend/domains/attraction/answer_program.py`
- Modify: `backend/domains/attraction/answer_validation.py`
- Modify: `backend/domains/attraction/selection_service.py`
- Modify: `backend/application/recommendation/group_selection.py`
- DSPy와 검증기는 0..limit를 허용하고, 관광 0개에 대해 공통 보정을 수행하지 않는다.

### Task 2: 관광 날씨 Context

- Create: `backend/domains/attraction/weather_reranker.py`
- Modify: `backend/domains/attraction/recommendation_pipeline.py`
- Modify: `backend/domains/attraction/agent.py`
- Modify: `backend/domains/attraction/answer_evidence.py`
- 방문 날짜·날씨 요청이 있을 때 Provider를 호출하고, 실패 시 기존 후보를 보존한다.

### Task 2.1: 카페형 Agent 경계와 Context Enricher

- Create: `backend/domains/attraction/context_enricher.py`
- Modify: `backend/domains/attraction/recommendation_pipeline.py`
- Modify: `backend/domains/attraction/agent.py`
- Agent에서 위치 해석·MCP 선택 로직을 제거하고 Context Enricher가 후보 좌표 기반 혼잡도와 요청 기반 날씨를 처리한다.

### Task 3: 직접 회귀 검증

- 0개 선택이 공통 보정에서 보존되는지 일회성 실행으로 확인한다.
- 날씨 성공·실패 후보 신호를 일회성 실행으로 확인한다.
- 실행 중인 서버가 있으면 구조화 API와 관광 응답을 호출하고, 없으면 도메인 경계까지 검증한다.
