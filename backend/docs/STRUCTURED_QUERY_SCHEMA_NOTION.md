# SeoulMate 사용자 질문 → Structured Query JSON 명세

> 첫 번째 GPT가 사용자 질문을 받아 백엔드의 RAG, MCP, 루트 생성기가 사용할 JSON으로 변환하는 구조

---

## 1. 문서 목적

SeoulMate는 사용자의 자연어 질문을 바로 검색하지 않는다. 첫 번째 GPT가 질문을 구조화된
`StructuredTravelQuery` JSON으로 변환하고, 백엔드는 이 JSON을 검증한 뒤 RAG·MCP·최종 GPT를 실행한다.

```text
사용자 자연어 질문
→ gpt-4o-mini Structured Query Parser
→ StructuredTravelQuery JSON
→ 백엔드 스키마 검증 및 누락값 보정
→ Task별 도메인 검색
→ 필요한 경우 MCP 호출
→ 도메인별 재랭킹
→ 최종 GPT 후보 선택 및 답변 생성
→ 프론트엔드 응답
```

첫 GPT JSON은 **사용자에게 보여주는 답변이 아니라 백엔드 실행 계획**이다.

---

## 2. 전체 JSON 구조

```json
{
  "language": "ko",
  "intent": "single_place_recommendation",
  "original_question": "내일 저녁 홍대에서 조용한 중식당 추천해줘",
  "normalized_question": "내일 저녁 홍대의 조용한 중식당 추천",
  "tasks": [
    {
      "task_id": "task_1",
      "domain": "restaurant",
      "search_query": "홍대 조용한 중식당",
      "themes": ["조용한", "대화하기 좋은"],
      "desired_count": 3,
      "notes": null,
      "slot_id": null,
      "day_number": null,
      "visit_date": null,
      "start_time": null,
      "end_date": null,
      "end_time": null,
      "filters": null
    }
  ],
  "filters": {
    "location": "홍대",
    "radius_km": null,
    "is_active": true,
    "start_date": "2026-07-16",
    "end_date": "2026-07-16",
    "time_window": "evening",
    "party_size": null,
    "budget_min_krw": null,
    "budget_max_krw": null,
    "transportation": [],
    "accessibility": [],
    "required_features": [],
    "excluded_features": []
  },
  "source_mode": "rag_mcp",
  "weather_request": {
    "query": "내일 저녁 홍대에서 조용한 중식당 추천해줘",
    "location_name": "홍대",
    "target_date": "2026-07-16",
    "target_time": "evening",
    "language": "ko"
  },
  "route_request": null,
  "general_response_instruction": null
}
```

---

## 3. 최상위 필드 요약

| 필드 | 타입 | 필수 | 역할 |
|---|---|---:|---|
| `language` | string | 권장 | 사용자 질문 및 최종 답변 언어 |
| `intent` | string | 필수 | 전체 실행 경로 결정 |
| `original_question` | string | 필수 | 사용자 원문 보존 |
| `normalized_question` | string | 필수 | 검색 목적을 정리한 문장 |
| `tasks` | array | 조건부 | 도메인별 검색 단위 |
| `filters` | object | 필수 | 모든 Task에 공통인 필터 |
| `source_mode` | string/null | 권장 | RAG와 MCP 사용 여부 |
| `weather_request` | object/null | 조건부 | 날씨 MCP 요청 정보 |
| `route_request` | object/null | 조건부 | 당일·다일 루트 전체 조건 |
| `general_response_instruction` | string/null | 조건부 | 일반 답변 생성 지시 |

---

## 4. `language`

```json
"language": "ko"
```

지원 값:

| 값 | 의미 | 검색 대상 |
|---|---|---|
| `ko` | 한국어 | 한글 식당·리뷰·메뉴 테이블 |
| `en` | 영어 | 영어 식당·리뷰·메뉴 테이블 |

실제 GPT가 영어 질문에 `ko`를 반환할 수 있다. 백엔드는 사용자 원문의 한글과 영문 비율을
검사해 명백한 영어 질문이면 `effective_query_language="en"`으로 보정한다.

---

## 5. `intent`

`intent`는 질문의 전체 실행 경로를 결정한다.

| 값 | 의미 | Task | MCP |
|---|---|---|---|
| `single_place_recommendation` | 하나 또는 소수 장소 추천 | 있음 | 선택적 |
| `day_trip_route` | 숙박 없는 당일 일정 | 있음 | 선택적 |
| `multi_day_route` | 1박 이상 일정 | 있음 | 선택적 |
| `weather_information` | 장소 추천 없이 날씨 조회 | 없음 | 사용 |
| `general_response` | 검색·날씨가 필요 없는 일반 질문 | 없음 | 없음 |

### Intent 예시

```text
“홍대 중식당 추천해줘”
→ single_place_recommendation

“내일 홍대에서 저녁 먹고 카페도 가는 코스 짜줘”
→ day_trip_route

“서울 2박 3일 일정 짜줘”
→ multi_day_route

“내일 서울 날씨 알려줘”
→ weather_information

“서울은 왜 대한민국의 수도야?”
→ general_response
```

---

## 6. `original_question`

```json
"original_question": "내일 저녁 홍대에서 조용한 중식당 추천해줘"
```

사용자 질문을 수정하지 않고 그대로 보관한다.

백엔드에서 사용하는 곳:

- GPT가 누락한 평점·시설·예산 조건 복구
- 날짜·시간 검증
- 날씨 적용 여부 판단
- Weather MCP 질의
- 최종 GPT 답변 생성
- 디버깅과 감사 로그

첫 GPT가 구조화 필드를 잘못 만들더라도 사용자 원문을 이용해 일부 조건을 복구할 수 있다.

---

## 7. `normalized_question`

```json
"normalized_question": "내일 저녁 홍대의 조용한 중식당 추천"
```

질문의 의미를 정리한 문장이다. 디버깅과 전체 의미 파악에 사용한다.

실제 벡터 검색은 주로 `tasks[].search_query`, `tasks[].themes`, 필터를 조합해 만든 검색 계획을 사용한다.

---

## 8. `tasks`

Task는 독립적으로 장소를 검색해야 하는 최소 단위다.

```json
{
  "task_id": "task_1",
  "domain": "restaurant",
  "search_query": "홍대 조용한 중식당",
  "themes": ["조용한", "대화하기 좋은"],
  "desired_count": 3,
  "notes": null,
  "slot_id": null,
  "day_number": null,
  "visit_date": null,
  "start_time": null,
  "end_date": null,
  "end_time": null,
  "filters": null
}
```

### Task 필드

| 필드 | 타입 | 역할 |
|---|---|---|
| `task_id` | string | 요청 안에서 Task를 구분하는 ID |
| `domain` | string | 검색 담당 도메인 |
| `search_query` | string | 도메인 검색기에 전달할 핵심 검색 문장 |
| `themes` | string[] | 분위기·목적·취향 등 의미 검색 신호 |
| `desired_count` | integer | 최종 선택지 개수. 단일 추천은 백엔드에서 항상 3으로 정규화 |
| `notes` | string/null | Task 보조 설명 |
| `slot_id` | string/null | 루트에서 방문 슬롯 식별자 |
| `day_number` | integer/null | 여행 중 몇 번째 날인지 |
| `visit_date` | date/null | 실제 방문 날짜 |
| `start_time` | string/null | 방문 시작 시각 |
| `end_date` | date/null | 숙박처럼 날짜를 넘기는 슬롯의 종료 날짜 |
| `end_time` | string/null | 방문 종료 시각 |
| `filters` | object/null | 해당 Task에만 적용되는 필터 |

### Domain 값

| 값 | 담당 기능 | 현재 상태 |
|---|---|---|
| `restaurant` | 식당 검색 | 실제 RAG 구현 |
| `cafe` | 카페 검색 | 팀 검색기 스켈레톤 |
| `accommodation` | 숙박 검색 | 팀 검색기 스켈레톤 |
| `attraction` | 문화시설 검색 | 팀 검색기 스켈레톤 |
| `etc` | 기타 장소 | 임시/확장용 |

날씨는 장소 검색 도메인이 아니다. GPT가 `domain="weather"` Task를 반환해도 백엔드 검증 단계에서
제거하고 `weather_request`를 사용한다.

### `search_query`

```json
"search_query": "홍대 조용한 중식당"
```

식당 도메인은 이 값을 그대로 한 번만 검색하지 않는다. 다음 세 종류로 나누어 검색한다.

```text
식당 벡터 검색어
리뷰 벡터 검색어
메뉴 벡터 검색어
```

예시:

```text
사용자 질문: 홍대에서 조용하고 대화하기 좋은 중식당

식당 검색: 조용한 중식당
리뷰 검색: 조용한 대화하기 좋은
메뉴 검색: 중식당
```

`떡볶이`, `쌀국수`, `마라탕`, `짜장면`처럼 사용자가 명시한 메뉴는 메뉴 테이블에서 실제 메뉴가
확인된 식당만 통과시킨다. 관련 있어 보이는 다른 음식점을 대신 추천하지 않는다.

### `themes`

```json
"themes": ["조용한", "대화하기 좋은"]
```

주로 벡터 검색에 사용하는 부드러운 조건이다.

적합한 예:

- 조용한
- 감성적인
- 데이트
- 대화하기 좋은
- 가족 모임
- 브런치

평점·예산·주차처럼 DB 컬럼으로 처리할 조건은 가능하면 `themes`가 아니라 `filters`에 넣는다.

### `desired_count`

```json
"desired_count": 3
```

일반 단일 장소 추천에서 사용자에게 보여줄 선택지 개수다. 제품 정책에 따라 항상 3으로
정규화한다. 사용자가 “한 곳 추천해줘”라고 표현하거나 첫 GPT가 `1`을 반환해도 백엔드 값은 `3`이 된다.

루트 Task는 의미가 다르다. 하나의 방문 슬롯에서 대표 장소 하나를 정하는 구조이므로
`desired_count=1`을 유지하고, Route Planner가 별도로 대안 2곳을 제공한다.

현재 식당 단일 선택 흐름:

```text
RAG 후보 최대 30개
→ 하드 필터 및 선택적 날씨 재랭킹
→ 최종 GPT 전달 최대 10개
→ 최종 GPT 선택 최대 3개
```

후보가 3개 이상이면 GPT는 3개를 선택한다. 후보가 1~2개뿐이면 존재하는 후보만 선택한다.
후보가 0개면 GPT를 호출하지 않는다.

---

## 9. 전역 `filters`

모든 Task에 공통으로 적용되는 조건이다.

```json
{
  "location": "홍대",
  "radius_km": 2.0,
  "is_active": true,
  "start_date": "2026-07-16",
  "end_date": "2026-07-16",
  "time_window": "evening",
  "party_size": 2,
  "budget_min_krw": null,
  "budget_max_krw": 30000,
  "transportation": [],
  "accessibility": [],
  "required_features": ["주차"],
  "excluded_features": []
}
```

### Filter 필드

| 필드 | 타입 | 역할 |
|---|---|---|
| `location` | string/null | 검색 지역 |
| `radius_km` | number/null | 검색 반경 |
| `is_active` | boolean/null | 운영 중인 장소 여부 |
| `start_date` | date/null | 방문 또는 여행 시작일 |
| `end_date` | date/null | 방문 또는 여행 종료일 |
| `time_window` | string/null | 아침·점심·저녁·밤 또는 시간대 |
| `party_size` | integer/null | 방문 인원 |
| `budget_min_krw` | integer/null | 최소 예산 |
| `budget_max_krw` | integer/null | 최대 예산 |
| `transportation` | string[] | 이동수단 관련 조건 |
| `accessibility` | string[] | 휠체어 등 접근성 조건 |
| `required_features` | string[] | 반드시 필요한 시설·특징 |
| `excluded_features` | string[] | 제외할 시설·특징 |

### 식당에서 실제 적용하는 필터

- 지역 및 반경
- 방문 날짜와 시간
- 현재 또는 방문 시점 영업 여부
- 평점 하한
- 메뉴 중앙가격
- 주차
- 반려동물 동반
- 키즈 메뉴
- 단체석
- 개인실
- 아기 의자
- 휠체어 접근성
- 제외 시설

### 하드 필터 원칙

```text
정보 없음 ≠ 조건 만족
정보 없음 ≠ 조건 불일치
```

사용자가 “주차 가능한 식당”을 명시하면 `has_parking=true`인 식당만 통과시킨다. 반대로 날씨
재랭킹처럼 보조 신호를 적용할 때는 주차 정보가 없다는 이유로 감점하지 않는다.

GPT가 질문에 없는 반경이나 시간 조건을 생성해도 백엔드는 원문과 비교해 신뢰할 수 없는 값을
무시한다.

---

## 10. Task별 `filters`

Task마다 지역·날짜·예산이 다를 때 사용한다.

```json
{
  "task_id": "task_1",
  "domain": "restaurant",
  "search_query": "홍대 저녁 식사",
  "themes": ["저녁"],
  "desired_count": 3,
  "filters": {
    "location": "홍대",
    "start_date": "2026-07-16",
    "time_window": "evening"
  }
}
```

필터 적용 순서:

```text
전역 filters
→ Task별 filters로 명시된 값만 덮어쓰기
→ 사용자 원문에서 명시 조건 복구
→ 도메인 검색 계획 생성
```

예를 들어 식당은 홍대, 카페는 연남동이면 각 Task의 `filters.location`을 다르게 설정한다.

---

## 11. `source_mode`

RAG와 MCP 사용 여부를 결정한다.

| 값 | 실행 방식 |
|---|---|
| `rag_only` | RAG 검색만 사용 |
| `rag_mcp` | RAG 검색 후 MCP 정보를 적용 |
| `mcp_only` | 장소 검색 없이 MCP만 사용 |

### `rag_only`

```json
"source_mode": "rag_only"
```

```text
RAG 검색
→ 날씨 호출 안 함
→ 날씨 재랭킹 안 함
→ 최종 GPT 후보 선택
```

### `rag_mcp`

```json
"source_mode": "rag_mcp"
```

```text
RAG 검색
→ Weather MCP
→ 식당 데이터와 날씨를 조합한 재랭킹
→ 최종 GPT 후보 선택
```

### `mcp_only`

```json
"source_mode": "mcp_only"
```

날씨만 묻는 질문처럼 장소 DB 검색이 필요 없을 때 사용한다.

### 누락 보정

실제 `gpt-4o-mini` 테스트에서 `source_mode`가 누락되는 경우가 있었다. 백엔드는 다음 정보를 사용해
다시 결정한다.

- `intent`
- Task 존재 여부
- 날짜·시간 표현
- 날씨 관련 표현
- `weather_request` 존재 여부

---

## 12. `weather_request`

실제 날씨가 필요한 경우에만 생성한다.

```json
{
  "query": "내일 저녁 홍대에서 조용한 중식당 추천해줘",
  "location_name": "홍대",
  "target_date": "2026-07-16",
  "target_time": "evening",
  "language": "ko"
}
```

| 필드 | 역할 |
|---|---|
| `query` | 날짜·시간 표현을 보존한 원문 기반 질의 |
| `location_name` | 사용자가 지정한 날씨 조회 지역 |
| `target_date` | 조회할 날짜 |
| `target_time` | 조회할 시각 또는 시간대 |
| `language` | 날씨 출력 언어 |

Weather MCP 입력:

- 지역명
- 지오코딩된 위도·경도
- 날짜
- 방문 시각
- 언어
- 사용자 질문

Weather MCP는 날씨 사실과 중립적인 태그를 반환한다. MCP가 식당 점수를 직접 계산하지 않는다.
식당 재랭커가 메뉴·거리·주차·야외 시설과 날씨를 조합한다.

### 날씨 적용 원칙

- `rag_only`에서는 날씨 점수를 만들지 않는다.
- `rag_mcp`에서만 날씨를 재랭킹에 반영한다.
- 실제 예보가 맑으면 사용자가 “비가 오면”이라고 말해도 비로 조작하지 않는다.
- 날씨 정보가 실패하면 원래 RAG 순서를 유지한다.
- 날씨는 후보를 제거하는 절대 필터가 아니라 보조 신호다.

---

## 13. 단일 식당 추천 예시

### 사용자 질문

```text
홍대에서 평점 4.0 이상이고 주차 가능한 중식당 추천해줘.
```

### 첫 GPT JSON

```json
{
  "language": "ko",
  "intent": "single_place_recommendation",
  "original_question": "홍대에서 평점 4.0 이상이고 주차 가능한 중식당 추천해줘.",
  "normalized_question": "홍대의 평점 4.0 이상 주차 가능한 중식당 추천",
  "tasks": [
    {
      "task_id": "task_1",
      "domain": "restaurant",
      "search_query": "홍대 중식당",
      "themes": [],
      "desired_count": 3,
      "notes": null,
      "slot_id": null,
      "day_number": null,
      "visit_date": null,
      "start_time": null,
      "end_date": null,
      "end_time": null,
      "filters": null
    }
  ],
  "filters": {
    "location": "홍대",
    "radius_km": null,
    "is_active": true,
    "start_date": null,
    "end_date": null,
    "time_window": null,
    "party_size": null,
    "budget_min_krw": null,
    "budget_max_krw": null,
    "transportation": [],
    "accessibility": [],
    "required_features": ["주차"],
    "excluded_features": []
  },
  "source_mode": "rag_only",
  "weather_request": null,
  "route_request": null,
  "general_response_instruction": null
}
```

백엔드는 원문의 `평점 4.0 이상`을 복구해 `min_rating=4.0`으로 적용한다.

---

## 14. 식당과 카페 복합 추천 예시

### 사용자 질문

```text
내일 홍대에서 저녁을 먹고 분위기 좋은 카페 한 곳도 가고 싶어.
```

### 첫 GPT JSON

```json
{
  "language": "ko",
  "intent": "day_trip_route",
  "original_question": "내일 홍대에서 저녁을 먹고 분위기 좋은 카페 한 곳도 가고 싶어.",
  "normalized_question": "내일 홍대에서 저녁 식사 후 분위기 좋은 카페 방문",
  "tasks": [
    {
      "task_id": "task_1",
      "domain": "restaurant",
      "search_query": "홍대 저녁 식사",
      "themes": ["저녁", "식사"],
      "desired_count": 1,
      "notes": null,
      "slot_id": "d1-restaurant-1",
      "day_number": 1,
      "visit_date": "2026-07-16",
      "start_time": "19:00",
      "end_date": null,
      "end_time": "20:30",
      "filters": null
    },
    {
      "task_id": "task_2",
      "domain": "cafe",
      "search_query": "홍대 분위기 좋은 카페",
      "themes": ["분위기 좋은"],
      "desired_count": 1,
      "notes": null,
      "slot_id": "d1-cafe-1",
      "day_number": 1,
      "visit_date": "2026-07-16",
      "start_time": "21:00",
      "end_date": null,
      "end_time": "22:00",
      "filters": null
    }
  ],
  "filters": {
    "location": "홍대",
    "radius_km": null,
    "is_active": true,
    "start_date": "2026-07-16",
    "end_date": "2026-07-16",
    "time_window": null,
    "party_size": null,
    "budget_min_krw": null,
    "budget_max_krw": null,
    "transportation": [],
    "accessibility": [],
    "required_features": [],
    "excluded_features": []
  },
  "source_mode": "rag_mcp",
  "weather_request": {
    "query": "내일 홍대에서 저녁을 먹고 분위기 좋은 카페 한 곳도 가고 싶어.",
    "location_name": "홍대",
    "target_date": "2026-07-16",
    "target_time": null,
    "language": "ko"
  },
  "route_request": {
    "destination": "홍대",
    "period": {
      "start_date": "2026-07-16",
      "end_date": "2026-07-16",
      "nights": 0,
      "days": 1
    },
    "adults": 1,
    "children": 0,
    "arrival_at": null,
    "arrival_location": null,
    "departure_at": null,
    "departure_location": null,
    "accommodation_id": null,
    "preferred_accommodation_areas": [],
    "pace": "normal",
    "max_places_per_day": 5,
    "target_places_per_day": 2,
    "transportation": [],
    "budget": {
      "total_krw": null,
      "daily_krw": null,
      "accommodation_total_krw": null,
      "meal_per_person_krw": null
    },
    "preferred_areas": ["홍대"],
    "preferred_themes": ["분위기 좋은"],
    "required_features": [],
    "excluded_features": [],
    "must_visit": [],
    "avoid_places": []
  },
  "general_response_instruction": null
}
```

Task는 도메인별로 분리된다.

```text
task_1 → RestaurantSearchService
task_2 → CafeSearchService
```

각 도메인에서 별도 후보를 검색하고 Route Planner가 방문 순서를 조합한다.

---

## 15. `route_request`

당일 또는 몇 박 며칠 여행의 전체 조건이다.

```json
{
  "destination": "서울",
  "period": {
    "start_date": "2026-07-16",
    "end_date": "2026-07-17",
    "nights": 1,
    "days": 2
  },
  "adults": 2,
  "children": 0,
  "arrival_at": "10:00",
  "arrival_location": "서울역",
  "departure_at": "20:00",
  "departure_location": "서울역",
  "accommodation_id": null,
  "preferred_accommodation_areas": [],
  "pace": "normal",
  "max_places_per_day": 5,
  "target_places_per_day": null,
  "transportation": ["지하철"],
  "budget": {
    "total_krw": null,
    "daily_krw": null,
    "accommodation_total_krw": null,
    "meal_per_person_krw": null
  },
  "preferred_areas": ["홍대"],
  "preferred_themes": ["감성", "맛집"],
  "required_features": [],
  "excluded_features": [],
  "must_visit": [],
  "avoid_places": []
}
```

### RouteRequest 필드

| 필드 | 역할 |
|---|---|
| `destination` | 전체 여행 목적지 |
| `period` | 시작일·종료일·박·일 수 |
| `adults`, `children` | 여행 인원 |
| `arrival_at`, `arrival_location` | 도착 시각과 장소 |
| `departure_at`, `departure_location` | 출발 시각과 장소 |
| `accommodation_id` | 이미 선택한 숙박 ID |
| `preferred_accommodation_areas` | 선호 숙박 지역 |
| `pace` | `relaxed`, `normal`, `packed` |
| `max_places_per_day` | 하루 장소 수의 안전 상한. 실제 목표 개수가 아님 |
| `target_places_per_day` | 당일 루트에서 사용자가 원하는 정확한 장소 수. 생략 가능하지만 신규 GPT는 채우는 것을 권장 |
| `transportation` | 이동수단 |
| `budget` | 전체·일별·숙박·식사 예산 |
| `preferred_areas` | 선호 지역 |
| `preferred_themes` | 여행 테마 |
| `required_features` | 필수 조건 |
| `excluded_features` | 제외 조건 |
| `must_visit` | 반드시 방문할 장소 |
| `avoid_places` | 피할 장소 |

### 루트 제한

- 최대 7일
- 하루 최대 5개 슬롯
- 전체 최대 35개 Task
- 슬롯당 Route Planner 전달 후보 최대 5개
- 슬롯별 대표 장소 1곳
- 슬롯별 대안 최대 2곳
- 전체 대안 루트는 기본적으로 생성하지 않음

### 당일 루트의 장소 수

`max_places_per_day`와 `target_places_per_day`는 역할이 다르다.

```text
max_places_per_day = 허용 상한
target_places_per_day = 이번 요청에서 실제로 만들 장소 수
Task 개수 = 실제 방문 슬롯 수
```

- “저녁 식당과 카페를 가고 싶다” → Task 2개, `target_places_per_day=2`
- “하루 5곳 루트를 짜줘” → Task 5개, `target_places_per_day=5`
- 당일 루트에서 `target_places_per_day`가 있으면 Task 수와 정확히 같아야 한다.
- 필드가 없는 기존 JSON은 계속 허용하며, 이때는 Task 수가 곧 루트 장소 수다.
- 각 루트 Task의 `desired_count`는 `1`이다. 백엔드는 슬롯별 검색 후보 5개 중 대표 1곳과 대안 2곳을 고른다.

### 루트 Task 누락 보정

GPT가 다음 값을 생략할 수 있다.

- `slot_id`
- `day_number`
- `visit_date`
- 숙박 `end_date`
- 숙박 `end_time`

백엔드는 여행 기간과 Task 순서를 기준으로 보정한다.

```text
slot_id: d{day_number}-{domain}-{순번}
숙박 end_date: visit_date + 1일
숙박 end_time: 기본 08:00
```

---

## 16. 날씨만 묻는 질문 예시

### 사용자 질문

```text
내일 오후 3시 홍대 날씨 알려줘.
```

### JSON

```json
{
  "language": "ko",
  "intent": "weather_information",
  "original_question": "내일 오후 3시 홍대 날씨 알려줘.",
  "normalized_question": "내일 15시 홍대 날씨",
  "tasks": [],
  "filters": {
    "location": "홍대",
    "radius_km": null,
    "is_active": null,
    "start_date": "2026-07-16",
    "end_date": "2026-07-16",
    "time_window": "15:00",
    "party_size": null,
    "budget_min_krw": null,
    "budget_max_krw": null,
    "transportation": [],
    "accessibility": [],
    "required_features": [],
    "excluded_features": []
  },
  "source_mode": "mcp_only",
  "weather_request": {
    "query": "내일 오후 3시 홍대 날씨 알려줘.",
    "location_name": "홍대",
    "target_date": "2026-07-16",
    "target_time": "15:00",
    "language": "ko"
  },
  "route_request": null,
  "general_response_instruction": null
}
```

장소 추천이 없으므로 `tasks=[]`, `source_mode="mcp_only"`다.

---

## 17. 일반 답변 예시

### 사용자 질문

```text
서울은 왜 대한민국의 수도야?
```

### JSON

```json
{
  "language": "ko",
  "intent": "general_response",
  "original_question": "서울은 왜 대한민국의 수도야?",
  "normalized_question": "서울이 대한민국의 수도인 이유",
  "tasks": [],
  "filters": {},
  "source_mode": null,
  "weather_request": null,
  "route_request": null,
  "general_response_instruction": "서울의 역사적·행정적 배경을 설명한다."
}
```

RAG와 MCP를 사용하지 않고 일반 답변 생성기로 전달한다.

---

## 18. 백엔드 검증과 보정

첫 GPT JSON을 그대로 신뢰하지 않는다. Pydantic 스키마와 코드 정책으로 검증한다.

### 자동 검증

- `task_id` 중복 금지
- 일반 추천 Task 최대 5개
- 루트 최대 7일
- 하루 최대 5개 슬롯
- 날짜 범위와 `nights`, `days` 일치
- 최소 예산이 최대 예산보다 높을 수 없음
- `start_date`가 `end_date`보다 늦을 수 없음
- 동일 슬롯에 같은 장소 중복 금지

### 자동 보정

- 영어 질문인데 `language="ko"`이면 영어 검색으로 보정
- `source_mode`가 없으면 질문과 구조를 보고 재결정
- 날씨 Task가 있으면 장소 Task에서 제거
- Task 지역이 전역 지역과 다르면 Task별 지역 우선
- 루트의 `slot_id`, 날짜, 일차 누락 보완
- 숙박 체크아웃 날짜·시간 누락 보완
- 질문에 없는 반경·시간 필터 무시
- 원문에 명시된 평점·시설·예산을 검색 계획에서 복구

---

## 19. JSON이 실제 검색에 사용되는 위치

| JSON 값 | 사용하는 곳 | 역할 |
|---|---|---|
| `intent` | Chat/Route Router | 실행 경로 선택 |
| `language` | 도메인 검색기·최종 GPT | DB 언어와 답변 언어 |
| `original_question` | 검색 정책·MCP·최종 GPT | 누락 조건 복구 및 원문 유지 |
| `tasks[].domain` | Domain Registry | 검색기 선택 |
| `tasks[].search_query` | RAG | 식당·리뷰·메뉴 검색어 생성 |
| `tasks[].themes` | RAG | 분위기·목적 의미 검색 |
| `tasks[].desired_count` | 후보·응답 정책 | 단일 추천은 3, 루트 슬롯은 1 |
| 전역·Task `filters` | 검색 계획 | 하드 필터 및 위치·시간 적용 |
| `source_mode` | Tool Policy | MCP 호출 여부 |
| `weather_request` | Weather MCP Client | 날짜·시간·지역 조회 |
| `route_request` | Route Service | 여행 기간·인원·예산·속도 |
| Task 슬롯 필드 | Route Planner | 날짜별 방문 슬롯 구성 |
| `general_response_instruction` | 일반 답변 생성기 | 검색 없는 답변 지시 |

---

## 20. 최종 GPT에 전달되는 정보

첫 GPT JSON 전체를 최종 GPT가 마음대로 수정하는 것이 아니다. 백엔드가 검증한 후보와 필요한
구조화 문맥만 전달한다.

식당 후보당 주요 전달 정보:

```json
{
  "restaurant_id": "9413973",
  "name": "목란",
  "category": "중국 요리",
  "rating": 4.1,
  "review_count": 100,
  "distance_km": 1.4,
  "menu_price_median_krw": 42000,
  "confirmed_features": ["parking", "group_seating", "private_room"],
  "menus": ["동파육", "멘보샤", "짬뽕"],
  "reviews": ["검증된 리뷰 근거"],
  "weather_reasons": []
}
```

최종 GPT의 역할:

- 전달받은 상위 후보 안에서 최대 3개 선택
- 사용자에게 보여줄 선정 이유 생성
- 자연스러운 최종 답변 생성

최종 GPT가 반환한 `restaurant_id`는 반드시 전달 후보 ID 목록에 포함되어야 한다. 잘못된 ID,
중복 ID, 빈 이유는 서버가 제거·복구한다.

프론트엔드는 `restaurant_id`로 상세 API를 호출하므로 채팅 응답에는 모든 상세 정보를 반복해서
넣지 않는다.

---

## 21. 후보가 없을 때

명시 메뉴나 필수 시설이 DB에 없으면 다른 장소를 억지로 추천하지 않는다.

예시:

```text
오늘 이태원에서 쌀국수 먹을 식당 추천해줘
```

실제 메뉴 테이블과 반경 조건을 만족하는 후보가 0개라면:

```json
{
  "answer": "요청하신 조건을 모두 만족하는 식당을 찾지 못했습니다. 검색 지역을 넓히거나 조건 하나를 완화해 주세요.",
  "selections": [],
  "no_candidates": true,
  "llm_fallback_used": false
}
```

후보가 없으면 최종 GPT도 호출하지 않는다.

---

## 22. 핵심 설계 원칙

1. 첫 GPT는 장소를 선택하지 않고 질문을 구조화한다.
2. 실제 장소는 도메인 DB와 RAG에서만 가져온다.
3. 검색기는 첫 사용자 문장을 처음부터 다시 자유롭게 파싱하지 않는다.
4. 전역 필터와 Task별 필터를 구분한다.
5. 질문에 없는 하드 필터를 만들지 않는다.
6. `rag_only`에서는 날씨를 호출하거나 점수에 반영하지 않는다.
7. `rag_mcp`에서만 실제 날씨를 재랭킹 보조 신호로 사용한다.
8. MCP는 사실과 태그를 제공하고 도메인 재랭커가 점수를 계산한다.
9. 명시 메뉴·시설이 확인되지 않으면 관련 있어 보이는 다른 장소로 대체하지 않는다.
10. 최종 GPT는 전달 후보 ID 안에서만 선택한다.
11. 후보가 없으면 GPT를 호출하지 않고 조건 완화를 요청한다.
12. 프론트엔드는 `domain + place_id` 또는 `restaurant_id`로 상세 API를 호출한다.

---

## 23. 관련 코드 위치

| 역할 | 파일 |
|---|---|
| Structured Query 스키마 | `schemas/structured_query.py` |
| 루트 요청 스키마 | `schemas/route_planner.py` |
| Structured Query 검색 정책 | `services/query_policy.py` |
| 식당 검색 계획·RRF | `services/rag.py` |
| 공통 검색 요청 변환 | `application/recommendation/request_factory.py` |
| 추천 Orchestrator | `application/recommendation/orchestrator.py` |
| Domain Registry | `domains/common/registry.py` |
| 식당 검색 서비스 | `domains/restaurant/search_service.py` |
| Weather MCP Client | `integrations/mcp/weather_client.py` |
| 식당 날씨 재랭킹 | `domains/restaurant/weather_policy.py` |
| 최종 GPT 선택·검증 | `services/llm.py` |
| 루트 생성·수정 | `application/route/` |

---

## 24. 한 문장 요약

```text
첫 GPT JSON은 사용자 질문을 intent, Task, 필터, 날씨 요청, 루트 요청으로 나눈 실행 계획이고,
실제 장소 선택은 검증된 DB 후보와 MCP 정보를 이용해 백엔드와 최종 GPT가 수행한다.
```
