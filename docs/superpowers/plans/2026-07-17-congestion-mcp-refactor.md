# Congestion MCP Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Weather MCP를 변경하지 않고 서울 위치 MCP의 다섯 도구를 책임별 모듈로 분리하고 Congestion 전용 연결 설정을 제공한다.

**Architecture:** 하나의 MCP 서버와 `/mcp` 엔드포인트는 유지한다. `server.py`는 앱 조립만 담당하고 장소 해석, 물품보관함, 혼잡도 도구는 별도 등록 모듈로 분리하며, 백엔드 Provider는 `CONGESTION_MCP_URL`로 독립 연결한다.

**Tech Stack:** Python 3.12, FastMCP, Starlette ASGI, httpx, Pydantic, unittest

## Global Constraints

- Weather MCP 파일과 `WEATHER_MCP_*` 설정을 변경하지 않는다.
- 기존 다섯 MCP Tool 이름과 입력·출력 계약을 유지한다.
- `ContextProvider`, `ContextResult`, `SearchCandidate` 계약을 변경하지 않는다.
- 서버 장애는 관광 추천 전체를 실패시키지 않는다.
- MCP 프로세스는 하나, 기본 포트는 8002를 사용한다.

---

### Task 1: Tool 계약 고정과 모듈 분리

**Files:**
- Create: `backend/mcp_servers/congestion/tools/place.py`
- Create: `backend/mcp_servers/congestion/tools/storage_locker.py`
- Create: `backend/mcp_servers/congestion/tools/congestion.py`
- Modify: `backend/mcp_servers/congestion/server.py`
- Test: `backend/tests/test_congestion_mcp_server.py`

- [x] 기존 다섯 Tool 이름을 검증하는 실패 테스트를 작성하고 실행한다.
- [x] 도구 등록 함수를 책임별 모듈로 이동하고 `server.py`에서 조립한다.
- [x] Tool 계약 테스트를 통과시킨다.

### Task 2: 독립 ASGI 실행 설정

**Files:**
- Modify: `backend/mcp_servers/congestion/server.py`
- Test: `backend/tests/test_congestion_mcp_server.py`

- [x] `/health`와 ASGI `app` 계약의 실패 테스트를 작성하고 실행한다.
- [x] `CONGESTION_MCP_HOST/PORT` 기반 Uvicorn 실행과 health gateway를 구현한다.
- [x] 서버 테스트를 통과시킨다.

### Task 3: Congestion 전용 클라이언트 연결

**Files:**
- Modify: `backend/integrations/mcp/congestion_client.py`
- Test: `backend/tests/test_congestion_mcp_client.py`

- [x] `CONGESTION_MCP_URL`, timeout, 실패 격리 테스트를 작성하고 실행한다.
- [x] 전용 URL과 선택적 Bearer 인증을 사용하는 클라이언트를 구현한다.
- [x] Congestion, 관광 재랭킹, 공통 실행기 회귀 테스트를 실행한다.
