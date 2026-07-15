# SeoulMate Backend

## 현재 백엔드 구조

```text
api/                 HTTP/SSE Router와 공용 dependency
application/         추천·루트 생성/수정 실행 흐름
domains/             식당 및 팀별 검색 알고리즘
integrations/        Weather/혼잡도 MCP, Booking, 보관소, Kakao
mcp_servers/         팀 공용 Weather/혼잡도 MCP 서버
schemas/             Structured Query·추천·루트 계약
services/            단계적 마이그레이션 중인 기존 실제 구현
```

식당 RAG, Weather MCP, 날씨 재랭킹, Route Planner는 새 구조에서 실제 구현에 연결되어 있습니다.
카페·숙박·문화시설·물품보관소·혼잡도·Booking.com은 팀원이 같은 계약으로 채울 수 있는
스켈레톤입니다. 전체 배치와 교체 방법은
[`docs/BACKEND_ARCHITECTURE_GUIDE.md`](docs/BACKEND_ARCHITECTURE_GUIDE.md)를 참고하세요.

새 구조의 실제 식당 연결 smoke test:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_target_architecture.py
.\.venv\Scripts\python.exe scripts\smoke_target_architecture.py --with-weather
```

## 검색 파이프라인

```text
RAG 식당 후보 30개
  → 질의에서 방문 시점 추출
  → 현재는 초단기실황, 오늘 저녁·내일은 해당 시각 단기예보 조회(10분 캐시)
  → 날씨 적합도 10%, 날씨·미래시점 명시 질의는 최대 20% 재랭킹
  → 상위 10개
  → OpenAI Responses API 최종 추천
  → POST /chat SSE
```

날씨 API가 실패하거나 `KMA_API_KEY`가 없으면 원래 RAG 순서를 그대로 사용합니다.

시간이 없는 `내일` 질의는 식당 방문 기본 시각인 저녁 19시를 사용합니다. `내일 점심`,
`오늘 저녁 7시`처럼 시간대가 있으면 해당 시각의 1시간 예보를 사용합니다.

## 실행

```powershell
Copy-Item .env.example .env
uv sync
uv run fastapi dev main.py
```

`.env`에 PostgreSQL, OpenAI, 카카오 REST API, 기상청 API 키를 설정해야 실제 검색이 동작합니다.

## 주요 API

- `GET /health`
- `GET /weather/context?lat=37.5665&lng=126.9780`
- `GET /weather/context?lat=37.5665&lng=126.9780&query=내일%20저녁%20갈%20식당`
- `POST /chat` (SSE)

## 테스트

```powershell
uv run python -m unittest discover -s tests -v
```
