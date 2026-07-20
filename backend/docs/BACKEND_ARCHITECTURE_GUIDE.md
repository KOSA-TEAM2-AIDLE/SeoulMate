# SeoulMate 백엔드 구조 및 팀 통합 가이드

> SeoulMate의 식당·카페·숙박·문화시설 검색과 날씨·혼잡도 MCP, Booking.com, 물품보관소 API를 하나의 백엔드에서 연결하기 위한 팀 공용 설계 문서

**문서 대상**

- 백엔드 공통 구조 담당자
- 식당·카페·숙박·문화시설 검색 담당자
- 날씨·혼잡도 MCP 담당자
- Booking.com·물품보관소 API 담당자

**현재 권장 상태**

- 공통 검색 계약과 Domain/Context Registry 구현 완료
- 실제 식당 RAG를 `RestaurantSearchService`로 연결 완료
- 실제 Weather MCP와 식당 날씨 재랭킹 연결 완료
- 실제 Route Planner create/edit application service 연결 완료
- 카페·숙박·문화시설·물품보관소·혼잡도·Booking.com은 스켈레톤 제공
- 팀원 검색기는 동일한 입력·출력 계약을 구현한 뒤 Registry 객체만 교체한다.

### 2026-07-15 실제 코드 배치 상태

| 기능 | 새 위치 | 상태 |
|---|---|---|
| 공통 검색 입력·후보 | `domains/common/models.py` | 구현 완료 |
| Domain Registry | `domains/common/registry.py` | 구현 완료 |
| 식당 PostgreSQL·벡터·RRF | `domains/restaurant/search_service.py` → `services/rag.py` | 실제 연결 |
| 식당 날씨 재랭킹 | `domains/restaurant/weather_policy.py` | 실제 연결 |
| Recommendation Orchestrator | `application/recommendation/orchestrator.py` | 구현 완료 |
| GPT ID 검증·복구 | `application/recommendation/candidate_selector.py` | 구현 완료 |
| Route create/edit | `application/route/` | 실제 Route Planner 연결 |
| Weather MCP Client | `integrations/mcp/weather_client.py` | 실제 연결 |
| Weather MCP Server | `mcp_servers/weather/server.py` | 실제 연결 |
| 카카오 지오코딩 | `integrations/kakao/geocoding_client.py` | 실제 연결 |
| 카페·숙박·문화시설 | `domains/cafe`, `domains/accommodation`, `domains/attraction` | 스켈레톤 |
| 물품보관소 | `domains/storage_locker`, `integrations/storage_locker` | 스켈레톤 |
| 혼잡도 MCP | `integrations/mcp/congestion_client.py`, `mcp_servers/congestion` | 스켈레톤 |
| Booking.com | `integrations/booking` | 스켈레톤 |

기존 import를 한 번에 삭제하지 않고 새 위치가 기존 구현을 호출하는 호환 어댑터 방식을 사용한다.
`routers/chat.py`의 식당 검색, 날씨 재랭킹, Weather MCP, Route Planner import는 이미 새 위치로
전환했다. 팀 구현이 안정되면 `services/rag.py` 내부 SQL과 벡터 함수를 파일별로 물리 분리한다.

---

## 빠른 탐색

- **전체 폴더 구성 확인:** 3. 목표 구조
- **각 폴더의 책임 확인:** 4. 계층별 책임
- **팀원이 맞춰야 할 입력·출력:** 5. 공통 검색 계약
- **검색기 등록 방법:** 6. Domain Registry
- **팀별 파일 위치:** 7. 도메인별 파일 위치와 역할
- **날씨·혼잡도 연동:** 8. 날씨·혼잡도 MCP 통합
- **Booking.com 연동:** 9. Booking.com API 통합
- **단일 추천 흐름:** 11. 단일 추천 실행 흐름
- **루트 생성·수정:** 12~13장
- **팀원별 할 일:** 16. 팀원별 구현 체크리스트
- **실제 적용 순서:** 18. 단계별 마이그레이션 순서

---

## 전체 구조 한눈에 보기

```text
사용자 질문 / Structured Query
        ↓
Chat Router
        ↓
Recommendation 또는 Route Orchestrator
        ↓
Domain Registry에서 검색기 선택
        ↓
식당 | 카페 | 숙박 | 문화시설 | 물품보관소
        ↓
필요한 경우 공통 컨텍스트 조회
        ↓
Weather MCP | Congestion MCP | Booking.com API
        ↓
도메인별 재랭킹
        ↓
GPT 최종 후보 선택과 이유 생성
        ↓
프론트엔드에 domain + place_id + 표시 정보 반환
```

---

## 1. 문서 목적

이 문서는 SeoulMate 백엔드에 다음 기능을 안정적으로 통합하기 위한 기준을 정의한다.

- 식당 단일 추천 및 RAG 검색
- 카페·숙박·문화시설 단일 추천
- 당일·다일 루트 생성과 프론트 로컬 편집
- 날씨 MCP
- 혼잡도 MCP
- 물품보관소 외부 API
- Booking.com 숙박 가용성 API
- 한국어·영어 응답

핵심 원칙은 모든 검색 알고리즘을 하나로 합치는 것이 아니다. 각 팀의 검색 알고리즘은 독립적으로 유지하되, 입력과 후보 출력 형식만 통일한다. 공통 오케스트레이터는 이 계약만 보고 검색기와 외부 도구를 조합한다.

---

## 2. 현재 구조의 상태

현재 백엔드는 식당 RAG, 날씨 재랭킹, Structured Query, 단일 추천, 다중 Task와 최초 루트 생성을 구현한다. 생성 이후 장소 삭제·삽입은 프론트 Zustand가 담당한다.

다만 `routers/chat.py`가 다음 책임을 동시에 갖고 있다.

- Structured Query 검증
- source mode 결정
- 식당 RAG 실행
- 미구현 도메인의 임시 후보 생성
- Weather MCP 호출
- 식당 날씨 재랭킹
- 다중 Task 처리
- 당일·다일 루트 생성
- 최초 루트 생성 결과 변환
- GPT 후보 선택과 답변 생성
- SSE 이벤트 생성

카페·숙박·문화시설 검색기와 혼잡도·Booking.com·물품보관소 연동이 추가되면 `chat.py`의 조건문과 의존성이 급격히 늘어난다. 따라서 HTTP, 실행 흐름, 도메인 검색, 외부 연동을 분리한다.

---

## 3. 목표 구조

```text
backend/
├─ main.py
│
├─ api/
│  ├─ routers/
│  │  ├─ chat.py
│  │  ├─ routes.py
│  │  ├─ restaurants.py
│  │  ├─ cafes.py
│  │  ├─ accommodations.py
│  │  ├─ attractions.py
│  │  ├─ storage_lockers.py
│  │  └─ health.py
│  └─ dependencies.py
│
├─ application/
│  ├─ recommendation/
│  │  ├─ orchestrator.py
│  │  ├─ candidate_selector.py
│  │  └─ response_builder.py
│  ├─ route/
│  │  ├─ create_service.py
│  │  ├─ edit_service.py
│  │  └─ route_planner.py
│  ├─ source_policy.py
│  └─ tool_policy.py
│
├─ domains/
│  ├─ common/
│  │  ├─ models.py
│  │  ├─ search_interface.py
│  │  ├─ reranker_interface.py
│  │  └─ registry.py
│  ├─ restaurant/
│  │  ├─ search_service.py
│  │  ├─ search_plan.py
│  │  ├─ repository.py
│  │  ├─ vector_search.py
│  │  ├─ reranker.py
│  │  ├─ weather_policy.py
│  │  └─ mapper.py
│  ├─ cafe/
│  │  ├─ search_service.py
│  │  ├─ repository.py
│  │  ├─ reranker.py
│  │  └─ mapper.py
│  ├─ accommodation/
│  │  ├─ search_service.py
│  │  ├─ repository.py
│  │  ├─ reranker.py
│  │  ├─ availability_service.py
│  │  └─ mapper.py
│  ├─ attraction/
│  │  ├─ search_service.py
│  │  ├─ repository.py
│  │  ├─ reranker.py
│  │  └─ mapper.py
│  └─ storage_locker/
│     ├─ search_service.py
│     ├─ reranker.py
│     └─ mapper.py
│
├─ integrations/
│  ├─ mcp/
│  │  ├─ base_client.py
│  │  ├─ weather_client.py
│  │  ├─ congestion_client.py
│  │  └─ registry.py
│  ├─ booking/
│  │  ├─ client.py
│  │  ├─ schemas.py
│  │  └─ mapper.py
│  ├─ storage_locker/
│  │  ├─ client.py
│  │  ├─ schemas.py
│  │  └─ mapper.py
│  └─ kakao/
│     └─ geocoding_client.py
│
├─ mcp_servers/
│  ├─ weather/
│  │  ├─ server.py
│  │  └─ weather_service.py
│  └─ congestion/
│     ├─ server.py
│     └─ congestion_service.py
│
├─ schemas/
│  ├─ chat.py
│  ├─ structured_query.py
│  ├─ recommendation.py
│  ├─ route.py
│  └─ integrations.py
│
├─ core/
│  ├─ config.py
│  ├─ exceptions.py
│  └─ logging.py
│
└─ tests/
   ├─ unit/
   ├─ integration/
   └─ end_to_end/
```

기존 코드를 즉시 모두 이동하지 않는다. 먼저 공통 인터페이스와 Registry를 만들고 기존 서비스를 감싼 뒤, 테스트를 통과시키면서 단계적으로 이동한다.

---

## 4. 계층별 책임

### 4.1 `api/routers`

HTTP 입력을 받고 application service에 전달한 뒤 HTTP 또는 SSE 응답으로 변환한다.

Router가 해서는 안 되는 일:

- SQL 실행
- 벡터 검색
- MCP 호출 조건 판단
- 날씨 점수 계산
- GPT 후보 검증
- 루트 알고리즘 실행

권장 형태:

```python
@router.post("/chat")
async def chat(body: ChatRequest):
    return StreamingResponse(
        recommendation_orchestrator.execute(body),
        media_type="text/event-stream",
    )
```

### 4.2 `application`

여러 도메인과 외부 서비스를 조합하는 실행 흐름을 담당한다.

`RecommendationOrchestrator`의 책임:

1. Structured Query 입력 검증
2. Task별 검색기 선택
3. Task별 후보 검색
4. 필요한 MCP·외부 API 결정
5. 도메인별 재랭킹 실행
6. GPT에 전달할 후보 생성
7. GPT가 반환한 ID·개수·중복 검증
8. 프론트엔드 응답 생성

`RouteService`의 책임:

1. Task를 방문 슬롯으로 변환
2. 슬롯별 도메인 검색 실행
3. 날짜·시간별 날씨 및 혼잡도 적용
4. 이동 거리와 앞뒤 장소를 고려한 루트 생성
5. 장소 하나와 대안 후보를 반환

### 4.3 `domains`

팀별 검색 알고리즘을 보관한다. 식당은 벡터 DB와 RRF, 카페는 자체 점수 모델, 숙박은 필터 기반 검색을 사용해도 된다.

각 도메인은 공통 입력을 받고 공통 후보 목록을 반환해야 한다.

### 4.4 `integrations`

외부 시스템에 접속한다.

- Weather MCP client
- Congestion MCP client
- Booking.com API client
- 물품보관소 API client
- 카카오 지오코딩 client

외부 응답 모델은 내부 검색 모델과 분리한다. 외부 API의 필드가 바뀌면 `client.py`, `schemas.py`, `mapper.py`만 수정되도록 구성한다.

### 4.5 `mcp_servers`

Weather MCP와 Congestion MCP 서버 자체를 보관한다. FastAPI 백엔드는 서버 내부 함수를 직접 import하지 않고 MCP client를 통해 호출한다.

이렇게 하면 식당·카페·숙박·문화시설 팀이 동일한 MCP를 공유할 수 있고, MCP 서버 장애가 도메인 검색 코드에 직접 전파되지 않는다.

---

## 5. 공통 검색 계약

### 5.1 검색 입력

```python
class DomainSearchRequest(BaseModel):
    task_id: str
    domain: str
    language: str

    search_query: str
    themes: list[str]

    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float | None = None

    visit_date: date | None = None
    start_time: str | None = None
    end_time: str | None = None

    party_size: int | None = None
    budget_min_krw: int | None = None
    budget_max_krw: int | None = None

    required_features: list[str] = []
    excluded_features: list[str] = []

    candidate_count: int = 10
```

Structured Query의 공통 필터와 Task별 필터를 병합한 후 검색기에 전달한다. 검색기가 최초 사용자 문장을 다시 파싱하지 않는 것이 원칙이다.

### 5.2 검색 후보

```python
class SearchCandidate(BaseModel):
    domain: str
    place_id: str
    task_id: str

    name: str
    category: str
    latitude: float | None = None
    longitude: float | None = None

    base_score: float
    final_score: float

    evidence: list[str] = []
    attributes: dict = {}
    signals: dict = {}
```

필드 의미:

- `place_id`: 프론트엔드 상세 API 호출용 ID
- `base_score`: 도메인 검색기가 계산한 원본 점수
- `final_score`: 날씨·혼잡도 등 재랭킹 이후 점수
- `evidence`: 검색 결과의 근거
- `attributes`: 가격·평점·시설·메뉴 등 도메인별 정보
- `signals`: 날씨 점수·혼잡도 점수·거리 점수 등 공통 보조 신호

식당 응답에서는 기존 프론트엔드 호환을 위해 `restaurant_id`를 유지하되, 내부에서는 `domain + place_id`를 공통 식별자로 사용한다.

### 5.3 검색 서비스 인터페이스

```python
from typing import Protocol

class DomainSearchService(Protocol):
    domain: str

    async def search(
        self,
        request: DomainSearchRequest,
    ) -> list[SearchCandidate]:
        ...
```

---

## 6. Domain Registry

도메인별 `if/elif` 분기를 만들지 않고 Registry에 검색기를 등록한다.

```python
DOMAIN_SEARCHERS = {
    "restaurant": RestaurantSearchService(...),
    "cafe": CafeSearchService(...),
    "accommodation": AccommodationSearchService(...),
    "attraction": AttractionSearchService(...),
    "storage_locker": StorageLockerSearchService(...),
}
```

오케스트레이터 호출:

```python
searcher = DOMAIN_SEARCHERS[task.domain]
candidates = await searcher.search(search_request)
```

팀원이 새 검색기를 추가할 때는 다음 작업만 수행한다.

1. 자기 도메인 폴더에 검색기 구현
2. 공통 `DomainSearchRequest`를 입력으로 사용
3. `SearchCandidate` 목록 반환
4. Registry에 검색기 한 줄 등록
5. 공통 계약 테스트 실행

`chat.py`, 루트 생성기, GPT 선택기를 수정하지 않아도 되어야 한다.

---

## 7. 도메인별 파일 위치와 역할

### 7.1 식당

```text
domains/restaurant/
├─ search_service.py   전체 검색 흐름
├─ search_plan.py      Structured Query → 식당 검색 계획
├─ repository.py       PostgreSQL 조회
├─ vector_search.py    식당·리뷰·메뉴 벡터 검색과 RRF
├─ reranker.py         평점·거리·가격·영업시간·시설 점수
├─ weather_policy.py   메뉴·주차·거리 기반 날씨 재랭킹
└─ mapper.py           식당 후보 → SearchCandidate
```

현재 `services/rag.py`는 위 파일로 단계적으로 분리한다. 처음에는 코드를 이동하지 않고 `RestaurantSearchService`가 기존 함수를 호출하도록 감싸는 것이 안전하다.

### 7.2 카페

```text
domains/cafe/
├─ search_service.py
├─ repository.py
├─ reranker.py
└─ mapper.py
```

카페 검색기는 조용함, 분위기, 좌석, 콘센트, 작업 가능 여부, 디저트, 테라스 등을 `attributes`에 담을 수 있다.

날씨를 적용할 경우 Weather MCP가 직접 점수를 주지 않는다. 카페의 `reranker.py`가 비·더위·추위와 실내 좌석·접근성·테라스 정보를 조합한다.

### 7.3 숙박

```text
domains/accommodation/
├─ search_service.py
├─ repository.py
├─ reranker.py
├─ availability_service.py
└─ mapper.py
```

숙박 DB 검색과 Booking.com 실시간 가용성 확인을 분리한다.

권장 순서:

```text
숙박 검색 후보 20개
→ 지역·평점·예산 필터
→ 상위 5~10개
→ Booking.com 일괄 가용성 확인
→ 예약 가능 여부 반영
→ GPT 후보 전달
```

Booking.com 응답을 벡터 검색 내부에 넣으면 안 된다. 외부 API 장애 시에도 숙박 검색 결과는 반환하되 `availability_status=unknown`으로 처리한다.

### 7.4 문화시설

내부 도메인 이름은 현재 Structured Query와 맞춰 `attraction`을 유지한다. 기존 `/events` API가 필요하면 호환용 Router로 남길 수 있다.

```text
domains/attraction/
├─ search_service.py
├─ repository.py
├─ reranker.py
└─ mapper.py
```

전시 기간, 휴관일, 운영시간, 실내·야외, 예약 필요 여부를 후보 속성으로 제공한다.

### 7.5 물품보관소

물품보관소 API 결과 자체가 검색 후보이므로 MCP 보조 정보가 아니라 독립된 도메인 검색기로 본다.

```text
integrations/storage_locker/client.py
    ↓ 외부 API 호출
integrations/storage_locker/schemas.py
    ↓ 외부 응답 검증
domains/storage_locker/mapper.py
    ↓ SearchCandidate 변환
domains/storage_locker/search_service.py
    ↓ 거리·영업시간·크기·이용 가능 여부 정렬
```

Structured Query의 Domain에는 장기적으로 `storage_locker`를 추가한다. GPT 출력 변경 전에는 `domain=etc`이면서 보관소 키워드가 있는 Task를 백엔드에서 `storage_locker`로 정규화할 수 있다.

---

## 8. 날씨·혼잡도 MCP 통합

날씨와 혼잡도는 검색 후보를 만드는 도메인이 아니라 후보 평가에 공통 정보를 제공하는 Context Provider다.

```python
class ContextProvider(Protocol):
    name: str

    async def get_context(
        self,
        request: ContextRequest,
    ) -> ContextResult:
        ...
```

```python
CONTEXT_PROVIDERS = {
    "weather": WeatherMCPProvider(...),
    "congestion": CongestionMCPProvider(...),
}
```

### Weather MCP 책임

- 위치·날짜·시간에 해당하는 날씨 조회
- 한국어·영어 시간 표현 처리
- 날씨 사실과 공통 태그 반환
- API 장애 시 `available=false` 반환

Weather MCP는 식당 점수나 카페 점수를 직접 계산하지 않는다.

예시:

```json
{
  "available": true,
  "temperature_c": 30,
  "condition": "rain",
  "wind_speed_mps": 6,
  "weather_tags": [
    "RAIN",
    "HOT",
    "OUTDOOR_UNFAVORABLE",
    "SHORT_WALKING_ROUTE_HELPFUL"
  ]
}
```

### Congestion MCP 책임

- 특정 지역·장소의 현재 또는 예상 혼잡도 조회
- 관측 시각과 데이터 신선도 제공
- 혼잡도 태그 반환

예시:

```json
{
  "available": true,
  "area_code": "POI013",
  "level": "crowded",
  "observed_at": "2026-07-15T18:10:00+09:00",
  "tags": [
    "CROWDED",
    "WAITING_RISK",
    "TRANSIT_DELAY_RISK"
  ]
}
```

### MCP 호출 단위

같은 지역·같은 방문 시각 후보마다 MCP를 반복 호출하지 않는다.

권장 캐시 키:

```text
provider + 지역 좌표 격자 + 방문 날짜 + 방문 시간대
```

날씨와 혼잡도 조회가 실패하면 기본 RAG 순서를 유지한다.

---

## 9. Booking.com API 통합

Booking.com은 숙박 도메인 전용 실시간 가용성 Provider다. 여러 도메인이 공통으로 사용하는 상황이 아니라면 MCP로 만들 필요가 없다.

```text
integrations/booking/
├─ client.py     HTTP 호출, 인증, timeout, retry
├─ schemas.py    외부 요청·응답 모델
└─ mapper.py     Booking 응답 → 내부 가용성 모델
```

호출 조건:

- 체크인·체크아웃 날짜가 있음
- 인원수가 있음
- 사용자가 예약 가능 여부를 명시적으로 요구함
- 실제 예약 직전 재확인이 필요함

단순한 “좋은 호텔 추천” 요청에서는 반드시 호출할 필요가 없다.

API 실패 처리:

- 숙박 검색 전체를 실패시키지 않는다.
- `availability_status=unknown`으로 표시한다.
- 확인되지 않은 후보를 “예약 가능”이라고 표현하지 않는다.
- 사용자에게 실시간 확인 실패 사실을 필요한 경우만 알린다.

---

## 10. source mode와 도구 정책

현재 모드:

- `rag_only`: 도메인 검색과 기본 재랭킹
- `rag_mcp`: 도메인 검색 후 날씨·혼잡도 보조 신호 적용
- `mcp_only`: 날씨·혼잡도 정보만 필요한 요청

하지만 `source_mode` 하나로 Booking.com과 물품보관소 API까지 제어하면 안 된다.

`application/tool_policy.py`에서 도구별 조건을 판단한다.

```python
class ToolExecutionPlan(BaseModel):
    use_weather: bool = False
    use_congestion: bool = False
    check_booking_availability: bool = False
    search_storage_lockers: bool = False
```

정책 예시:

```text
rag_only
→ 날씨·혼잡도 미사용

rag_mcp + 방문 날짜/시간 있음
→ 날씨 사용
→ 혼잡도 데이터가 지원하는 시간 범위면 혼잡도 사용

accommodation + 체크인/체크아웃 + 예약 가능 요구
→ Booking.com 사용

storage_locker Task
→ 물품보관소 API 사용
```

---

## 11. 단일 추천 실행 흐름

```text
프론트엔드 ChatRequest
→ StructuredTravelQuery 검증
→ Task별 공통 SearchRequest 생성
→ Domain Registry에서 검색기 선택
→ 도메인별 후보 검색
→ Tool Policy 생성
→ 필요 시 날씨·혼잡도 조회
→ 도메인별 재랭킹
→ 상위 N개를 GPT에 전달
→ GPT가 최종 후보 선택
→ 반환 ID가 후보 목록에 있는지 검증
→ domain + place_id + 선정 이유 반환
```

여러 Task가 있으면 Task별 후보를 섞지 않는다.

```text
식당 Task → 식당 후보 그룹
카페 Task → 카페 후보 그룹
숙박 Task → 숙박 후보 그룹
```

GPT도 각 그룹 안에서만 장소를 선택하게 한다.

---

## 12. 당일·다일 루트 생성

루트 요청에서 하나의 Task는 하나의 방문 슬롯을 의미한다.

```text
StructuredTravelQuery.tasks
→ 날짜·시간·도메인별 방문 슬롯 생성
→ 슬롯별 DomainSearchService 실행
→ 슬롯별 후보 5개 준비
→ 날씨·혼잡도 적용
→ RoutePlanner 실행
→ 슬롯당 장소 1개 + 대안 2개
→ 전체 루트 검증
```

검증 항목:

- 같은 장소의 불필요한 중복
- 운영시간
- 이동 시간
- 방문 순서
- 체크인·체크아웃 시간
- 날짜 범위
- 사용자 예산과 필수 시설
- 날씨가 나쁠 때 과도한 야외 이동

---

## 13. 생성된 루트 편집

최초 루트는 백엔드가 `travelPath`로 반환한다. 이후 사용자가 장소를 삭제하거나
단일 추천 장소를 특정 Day와 위치에 추가하는 작업은 프론트 Zustand에서 처리한다.

```text
장소 삭제 → removePathItem(day, placeId)
장소 삽입 → insertPathItem(day, index, place)
```

백엔드 저장, 루트 버전, 슬롯 교체 API는 사용하지 않는다. 상세 구현은
`docs/FRONTEND_ROUTE_MANUAL_INSERT_GUIDE_NOTION.md`를 참고한다.

---

## 14. 한국어·영어 데이터

식당 한국어·영어 DB 테이블은 기존 결정대로 분리한다. 공통 검색 계약은 DB 통합을 요구하지 않는다.

```python
if request.language == "en":
    restaurant_table = "restaurant_en"
    menu_table = "menu_en"
else:
    restaurant_table = "restaurant"
    menu_table = "menu"
```

각 도메인 팀은 자기 DB 구조에 맞춰 언어 테이블을 선택한다. 공통 오케스트레이터에는 요청 언어로 변환된 후보만 반환한다.

외부 API가 영어만 반환하는 경우 `mapper.py`에서 내부 코드와 표시 문구를 분리한다.

```json
{
  "availability_status": "available",
  "display_text": "예약 가능"
}
```

내부 판단에는 안정적인 코드 값을 사용하고, 사용자 출력만 언어에 맞게 변경한다.

---

## 15. 기존 파일 이동표

| 현재 파일 | 목표 위치 | 역할 |
|---|---|---|
| `main.py` | 유지 | 앱 생성과 Router 등록 |
| `routers/chat.py` | `api/routers/chat.py` | HTTP/SSE 처리만 유지 |
| `services/rag.py` | `domains/restaurant/`로 분리 | 식당 검색·DB·벡터 검색 |
| `services/query_policy.py` | `application/source_policy.py`, `domains/restaurant/search_plan.py` | 공통 정책과 식당 정책 분리 |
| `services/weather_reranker.py` | `domains/restaurant/weather_policy.py` | 식당 날씨 재랭킹 |
| `services/weather_mcp_client.py` | `integrations/mcp/weather_client.py` | Weather MCP 호출 |
| `weather_mcp_server.py` | `mcp_servers/weather/server.py` | Weather MCP 서버 |
| `services/weather.py` | `mcp_servers/weather/weather_service.py` | 기상청 API 처리 |
| `services/domain_agents.py` | `domains/common/registry.py`, `tests/mocks/` | Registry와 임시 검색기 분리 |
| `services/llm.py` | `candidate_selector.py`, `response_builder.py` | GPT 선택과 답변 생성 분리 |
| `services/route_planner.py` | `application/route/route_planner.py` | 루트 조합과 검증 |
| `services/mcp_tools.py` | MCP Registry로 교체 | 중복 MCP 호출 경로 제거 |

---

## 16. 팀원별 구현 체크리스트

### 카페 담당

- [ ] `CafeSearchService` 구현
- [ ] 공통 검색 입력 사용
- [ ] `SearchCandidate` 반환
- [ ] `place_id`를 상세 API ID와 일치시킴
- [ ] 한국어·영어 처리
- [ ] 조용함·분위기·좌석·테라스 등 근거 제공
- [ ] 날씨 적용은 Cafe Reranker에서 수행
- [ ] Registry 등록
- [ ] 계약 테스트 작성

### 숙박 담당

- [ ] `AccommodationSearchService` 구현
- [ ] 체크인·체크아웃·인원·예산 필터 처리
- [ ] Booking.com Client 분리
- [ ] 후보를 줄인 후 Booking.com 호출
- [ ] 예약 가능·불가·알 수 없음 구분
- [ ] 외부 API 실패 시 기본 검색 유지
- [ ] Registry 등록
- [ ] 계약 테스트 작성

### 문화시설 담당

- [ ] `AttractionSearchService` 구현
- [ ] 전시 기간·휴관일·운영시간 처리
- [ ] 실내·야외·예약 필요 여부 제공
- [ ] 날짜·시간과 맞지 않는 시설 처리
- [ ] Registry 등록
- [ ] 계약 테스트 작성

### 혼잡도 MCP 담당

- [ ] 읽기 전용 MCP Tool 구현
- [ ] 위치 또는 area code 입력 계약 정의
- [ ] 관측 시각과 데이터 신선도 반환
- [ ] 공통 혼잡도 코드와 태그 반환
- [ ] timeout·retry·cache 구현
- [ ] 실패 시 `available=false` 반환
- [ ] `CongestionMCPProvider` 작성

### 물품보관소 담당

- [ ] 외부 API Client 구현
- [ ] 외부 응답 Pydantic Schema 작성
- [ ] 공통 후보 Mapper 작성
- [ ] 거리·운영시간·보관 크기 처리
- [ ] `StorageLockerSearchService` 구현
- [ ] Registry 등록
- [ ] API 장애 fallback 정책 작성

---

## 17. 테스트 기준

### Unit Test

- Task 필터 병합
- 도메인 Registry 선택
- 도메인별 Mapper
- 도메인별 재랭킹
- GPT 선택 ID 검증
- Booking.com 상태 변환
- Weather·Congestion 태그 해석

### Integration Test

- 실제 또는 Mock DB를 사용하는 검색
- MCP Client와 테스트 MCP Server 연결
- Booking.com Mock Server 연결
- 물품보관소 Mock API 연결
- API 장애·timeout·잘못된 응답 처리

### End-to-End Test 질문

```text
홍대에서 조용한 중식당 추천해줘.
내일 저녁 비가 오면 가기 좋은 식당 추천해줘.
성수에서 조용한 카페 한 곳 추천해줘.
내일 홍대에서 저녁을 먹고 분위기 좋은 카페도 가고 싶어.
이번 주말 2명이 예약 가능한 명동 호텔 추천해줘.
비 오는 날 가기 좋은 실내 문화시설 추천해줘.
서울역 근처 지금 이용 가능한 물품보관소 찾아줘.
내 루트의 두 번째 카페를 첫 번째 장소와 가까운 곳으로 바꿔줘.
```

각 테스트에서 확인할 정보:

- Structured Query 원본
- Task별 실제 RAG 입력값
- 도메인별 원본 후보 순위
- 적용된 필터와 제외 이유
- MCP 호출 여부와 요청 인자
- 날씨·혼잡도 적용 전후 순위
- Booking.com 조회 대상과 결과
- GPT에 전달한 후보
- GPT가 선택한 ID
- 최종 프론트엔드 응답

---

## 18. 단계별 마이그레이션 순서

### 1단계: 공통 계약

1. `DomainSearchRequest` 작성
2. `SearchCandidate` 작성
3. `DomainSearchService` Protocol 작성
4. Domain Registry 작성

### 2단계: 기존 식당 검색 감싸기

기존 `services/rag.py`를 바로 이동하지 않는다. `RestaurantSearchService`가 기존 함수를 호출하고 결과를 `SearchCandidate`로 변환하도록 만든다.

기존 테스트가 모두 통과하는지 확인한다.

### 3단계: 오케스트레이터 분리

`routers/chat.py`에서 다음 코드를 `application/`으로 옮긴다.

- Structured Task 실행
- 다중 Task 그룹 처리
- 단일 식당 추천
- 도구 호출 판단
- GPT 선택 검증
- 최초 루트 생성

Router에는 요청·응답 변환만 남긴다.

### 4단계: 임시 도메인 교체

기존 고정 응답을 `MockCafeSearchService`, `MockAccommodationSearchService`, `MockAttractionSearchService`로 등록한다.

팀원 검색기가 완성되면 Registry 등록 객체만 교체한다.

### 5단계: MCP 통합

Weather MCP와 Congestion MCP를 Context Registry에 등록한다. `services/mcp_tools.py`와 직접 함수 호출 경로는 제거한다.

### 6단계: 외부 API 통합

Booking.com과 물품보관소 API를 연결하고 timeout·cache·fallback 테스트를 추가한다.

### 7단계: 물리적 파일 이동

모든 기능과 테스트가 안정된 뒤 `rag.py`, `llm.py`, `weather.py`를 목표 폴더로 분리한다.

---

## 19. 최종 원칙

1. Router는 얇게 유지한다.
2. 최초 GPT가 만든 Structured Query를 검색기가 다시 자연어 파싱하지 않는다.
3. 도메인별 검색 알고리즘은 독립적으로 유지한다.
4. 검색 입력과 후보 출력 계약만 공통으로 맞춘다.
5. 날씨·혼잡도 MCP는 사실과 태그를 제공한다.
6. MCP가 도메인 점수를 직접 결정하지 않는다.
7. Booking.com은 숙박 후보를 줄인 뒤 호출한다.
8. 물품보관소 API는 독립 도메인 검색기로 취급한다.
9. 외부 서비스 실패 시 기본 RAG 결과를 유지한다.
10. GPT가 반환한 장소 ID는 반드시 전달 후보에 포함된 ID인지 검증한다.
11. 한국어·영어 DB 분리 정책을 유지한다.
12. 기존 코드는 인터페이스로 먼저 감싼 뒤 단계적으로 이동한다.
