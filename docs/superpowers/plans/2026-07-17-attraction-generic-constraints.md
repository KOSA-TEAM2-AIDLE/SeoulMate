# 관광 도메인 범용 제약조건 처리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 개별 개념 사전 없이 구조화된 `required_features`/`excluded_features`와 원문을 사용해 관광 후보의 조건을 처리하고, `물`-`박물관` 같은 부분 문자열 오탐을 방지한다.

**Architecture:** 공통 질의 파서는 변경하지 않고, 관광 도메인 내부에서 파싱된 요구·제외 문구를 후보 문서의 정규화된 어휘와 비교한다. 명시적 충돌만 결정적으로 제외하고, 애매한 조건은 원문과 함께 DSPy에 전달할 근거로 보존한다.

**Tech Stack:** Python 3.12, Pydantic, 기존 `DomainSearchRequest`/`SearchCandidate`

## Global Constraints

- `schemas`, `application.travel_query`, 다른 도메인은 변경하지 않는다.
- 개별 개념 알리아스와 충돌 용어 사전을 두지 않는다.
- 별도 테스트 파일과 Git 커밋을 생성하지 않는다.
- 명시적 문서 근거가 없는 후보는 제외하지 않는다.

---

### Task 1: 기존 개념 사전의 오탐 재현

**Files:**
- Inspect: `backend/domains/attraction/constraint_normalizer.py`
- Inspect: `backend/domains/attraction/constraint_evaluator.py`

**Interfaces:**
- Consumes: `excluded_features: list[str]`, `AttractionRecord`
- Produces: 기존 `물` 부분 일치와 사전 의존성을 보여주는 일회성 실행 결과

- [ ] `물`이 `박물관`에 잘못 매핑되는지, 사전에 없는 `대포소리`가 `unknown`이 되는지 일회성 Python 명령으로 확인한다.
- [ ] 실패가 기대한 원인에서 발생했는지 기록한다.

### Task 2: 범용 어휘 일치 구현

**Files:**
- Replace: `backend/domains/attraction/constraint_normalizer.py`
- Replace: `backend/domains/attraction/constraint_evaluator.py`

**Interfaces:**
- Produces: `normalize_constraint_text(text: str) -> str`
- Produces: `find_constraint_evidence(text: str, candidate_text: str) -> tuple[str, ...]`
- Produces: `evaluate_constraints(record, required_features, excluded_features) -> tuple[ConstraintAssessment, ...]`

- [ ] Unicode, 영문 대소문자, 공백을 정규화하는 작은 함수를 구현한다.
- [ ] 한글 한 글자·영문 단어는 단어 경계에서만 일치시킨다.
- [ ] 두 글자 이상 구는 정규화된 어구 일치로 판정하되, 임의의 개념 사전은 사용하지 않는다.
- [ ] `required`/`excluded` 구분과 원문 문구를 `ConstraintAssessment` 결과에 보존한다.

### Task 3: 관광 재랭킹에 연결

**Files:**
- Modify: `backend/domains/attraction/reranker.py`
- Modify: `backend/domains/attraction/mapper.py`

**Interfaces:**
- Consumes: `DomainSearchRequest.required_features`, `DomainSearchRequest.excluded_features`, `request.context["parsed_query"].original_question`
- Produces: `SearchCandidate.signals["constraint_assessments"]`

- [ ] 재랭커가 개념 정규화 없이 범용 평가기를 호출하도록 바꾼다.
- [ ] `excluded` 항목은 명시적 일치 근거가 있을 때만 제외한다.
- [ ] `required` 항목은 일치·미일치·불명으로 기록하고 DSPy에 전달할 신호로 보존한다.

### Task 4: 직접 실행 검증

**Files:**
- Verify only: existing attraction modules

**Interfaces:**
- Consumes: 일회성 Python 명령과 기존 관광 검색 서비스
- Produces: 실행 출력

- [ ] `물` 제외이 `박물관`을 충돌으로 판정하지 않는다.
- [ ] `실탄사격` 제외은 사전 등록 없이 동일 문구가 있는 후보만 제외한다.
- [ ] 사전에 없던 임의의 제약조건도 동일한 규칙으로 판정한다.
- [ ] 관광 외 도메인 모듈이 그대로 import되고 `git diff --check`가 통과하는지 확인한다.
