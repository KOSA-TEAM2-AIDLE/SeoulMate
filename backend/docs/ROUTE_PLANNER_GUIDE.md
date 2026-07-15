# SeoulMate Route Planner

## 결정된 출력 정책

- 사용자에게는 완성된 기본 루트 하나를 보여준다.
- 각 방문 슬롯은 후보 5곳 중 대표 1곳과 대안 최대 2곳을 가진다.
- 대표 장소는 기본 카드로, 대안은 접힌 UI로 표시한다.
- 전체 대안 루트는 함께 만들지 않는다. 사용자가 다른 코스를 요청할 때 별도로 다시 생성한다.
- GPT가 반환한 ID는 서버가 슬롯 후보 화이트리스트로 검증한다.
- 잘못된 ID, 중복 장소, 누락된 선택과 대안은 검색 순위로 복구한다.

## 당일 루트 입력

`intent`는 `day_trip_route`, 기간은 `nights=0`, `days=1`이다. 각 Task는 하나의 방문 슬롯이다.

```json
{
  "intent": "day_trip_route",
  "route_request": {
    "destination": "홍대",
    "period": {
      "start_date": "2026-07-16",
      "end_date": "2026-07-16",
      "nights": 0,
      "days": 1
    },
    "max_places_per_day": 5
  },
  "tasks": [
    {
      "task_id": "d1-dinner",
      "slot_id": "d1-dinner",
      "day_number": 1,
      "visit_date": "2026-07-16",
      "start_time": "19:00",
      "domain": "restaurant",
      "search_query": "홍대 저녁 식사",
      "themes": ["저녁", "분위기 좋은"],
      "desired_count": 1
    }
  ]
}
```

## 다일 루트 입력

`intent`는 `multi_day_route`이다. Task마다 `day_number`, `visit_date`, `start_time`을 명시한다. 날짜와 일차가 불일치하거나 하루 슬롯 수가 `max_places_per_day`를 넘으면 요청을 거부한다.

- 여행 기간: 최대 7일
- 하루 슬롯: 최대 5개
- 전체 슬롯: 최대 35개
- 슬롯별 검색 후보: 최대 5개
- 일반 장소 추천 Task: 최대 5개
- 루트 Task만 최대 35개

## SSE route 응답

`days[].slots[].place`가 대표 장소이고 `days[].slots[].alternatives`가 대안이다.

```json
{
  "time": "19:00",
  "category": "한식",
  "place": {
    "source_id": "9413973",
    "restaurant_id": "9413973",
    "name": "대표 식당",
    "rank": 1,
    "selection_reason": "저녁 동선과 요청 분위기에 가장 적합합니다."
  },
  "alternatives": [
    {
      "source_id": "8123456",
      "restaurant_id": "8123456",
      "name": "대안 식당",
      "rank": 2,
      "selection_reason": "가격을 우선할 때 적합한 대안입니다."
    }
  ]
}
```

## 날씨 적용

- `rag_only`: 날씨를 조회하거나 순위에 사용하지 않는다.
- `rag_mcp`: 식당 슬롯의 날짜와 시작 시각별로 Weather MCP를 조회한다.
- 동일 날짜·시각 조회는 요청 안에서 캐시한다.
- 예보 제공 범위를 벗어나거나 조회에 실패하면 날씨를 추측하지 않고 RAG 순위를 유지한다.
- 현재 카페·숙박·문화시설 Agent는 임시 후보이므로 도메인별 날씨 재랭킹은 팀 검색기 연결 후 추가한다.

## 단일 선택과 장애 fallback

- 루트 슬롯은 항상 대표 장소 하나만 확정한다.
- 후보가 1곳이면 대안은 0곳, 후보가 2곳이면 대안은 최대 1곳이다.
- 일반 식당 추천은 기존 제품 정책대로 상위 10개에서 최대 5곳을 보여준다. 실제 검색 후보가 5곳보다 적으면 있는 후보만 반환한다.
- OpenAI 최종 선택 호출이 실패해도 검증된 RAG 순서로 대표 장소와 대안을 구성한다.
- 숙박처럼 자정을 넘기는 슬롯은 `end_date`와 `end_time`을 함께 사용한다.

## 평가와 남은 과제

현재 구현은 ID 안전성, 슬롯 누락 복구, 중복 장소 방지, 당일·다일 배치, 슬롯별 날씨 시점, 단일 후보, GPT 장애 fallback과 저장 루트 단일 장소 교체를 검증한다. 자동 테스트 116개가 통과한다.

남은 우선순위는 다음과 같다.

1. 카페·숙박·문화시설 실제 Agent를 `RouteCandidate` 형식으로 연결한다.
2. 장소 간 이동시간 행렬을 후보 payload에 넣어 GPT가 직선거리 대신 실제 동선을 판단하게 한다.
3. 영업시간이 슬롯 시간을 포함하는지 서버에서 먼저 검증한다.
4. 20개 이상 슬롯의 입력 토큰과 응답 지연을 측정하고 필요하면 날짜 단위 2단계 편성으로 전환한다.
5. 사용자가 대안을 선택했을 때 뒤 슬롯 이동시간을 재검증하는 부분 루트 수정 API를 추가한다.
