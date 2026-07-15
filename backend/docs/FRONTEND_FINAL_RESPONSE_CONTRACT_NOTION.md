# SeoulMate 프론트 최종 응답 JSON 계약

> 첫 GPT가 만드는 `StructuredTravelQuery`와 다른 객체다. 이 문서의 JSON은 RAG·MCP·Route Planner·최종 GPT 처리가 끝난 뒤 프론트에 전달된다.

---

## 1. SSE 전달 형태

`POST /chat`은 SSE를 사용하므로 최종 화면 JSON은 `meta` 이벤트의 `result`에 들어간다.

```json
{
  "type": "meta",
  "intent": "both",
  "result": {
    "responseType": "recommendation",
    "day": null,
    "allDay": null,
    "travelPath": null,
    "recommendList": []
  }
}
```

프론트는 `event.result`만 화면 계약으로 사용한다. `places`, `days`, `reasons`, `sources`, `tool_results`는 기존 디버깅 및 하위 호환 필드다.

---

## 2. 단일 추천

```json
{
  "responseType": "recommendation",
  "day": null,
  "allDay": null,
  "travelPath": null,
  "recommendList": [
    {
      "id": "9413973",
      "name": "식당명",
      "category": "맛집",
      "subCategory": "한식",
      "address": "서울특별시 ...",
      "lat": 37.5665,
      "lng": 126.978,
      "rating": "4.5",
      "reviews": "1,824",
      "time": null,
      "image": null,
      "selectionReason": "사용자의 지역·메뉴·분위기 조건과 잘 맞습니다."
    }
  ]
}
```

규칙:

- `travelPath`는 반드시 `null`이다.
- `day`, `allDay`는 반드시 `null`이다.
- `recommendList`는 최종 순위 기준 최대 3개다.
- 유효 후보가 3개보다 적으면 장소를 복제하거나 생성하지 않는다.
- `id`는 도메인 상세 API 호출에 사용하는 실제 ID다.

---

## 3. 루트

```json
{
  "responseType": "route",
  "day": 1,
  "allDay": 2,
  "travelPath": {
    "1": [
      {
        "id": "REST005",
        "name": "명동교자 본점",
        "category": "맛집",
        "subCategory": "한식/칼국수",
        "address": "서울 중구 명동10길 29",
        "lat": 37.5626,
        "lng": 126.9854,
        "rating": "4.6",
        "reviews": "5,842",
        "time": "12:00 - 13:00",
        "image": null,
        "selectionReason": "첫 방문지와 다음 장소 사이의 동선과 점심 조건에 적합합니다."
      }
    ],
    "2": []
  },
  "recommendList": null
}
```

규칙:

- `recommendList`는 반드시 `null`이다.
- `allDay`는 `travelPath`의 키 개수와 정확히 같다.
- 키는 `"1"`부터 `allDay`까지 연속이어야 한다.
- `day`는 프론트가 처음 표시할 활성 일차이며 기본값은 1이다.
- 각 배열은 방문 시간순이다.
- `time`은 Route Planner의 `start_time`과 `end_time`으로 만든다.
- 루트 대안 2곳은 기존 디버그 `days[].slots[].alternatives`에 유지한다. 선택된 루트의 `travelPath`에는 대표 장소만 넣는다.

---

## 4. 날씨·일반 답변·오류

장소 카드가 없는 응답은 장소 필드를 모두 `null`로 둔다.

```json
{
  "responseType": "weather",
  "day": null,
  "allDay": null,
  "travelPath": null,
  "recommendList": null
}
```

`responseType` 허용값:

- `route`
- `recommendation`
- `weather`
- `general`
- `error`

---

## 5. 장소 필드의 데이터 소유권

| 필드 | 생성·복사 주체 |
|---|---|
| `id`, `name` | DB/API |
| `category`, `subCategory` | 도메인 검색 서비스 |
| `address`, `lat`, `lng` | DB/API |
| `rating`, `reviews` | DB/API 값을 백엔드가 표시 문자열로 변환 |
| `image` | DB/API |
| `time` | Route Planner |
| `selectionReason` | 최종 GPT가 선택 후보 ID와 함께 생성 |
| 채팅 답변 문장 | 최종 GPT |

GPT는 `address`, 좌표, 평점, 리뷰 수, 이미지 URL을 생성하거나 보완하면 안 된다. 원본 데이터가 없으면 `null`이다.

---

## 6. 프론트 분기 예시

```javascript
const result = event.result;

if (result.responseType === 'recommendation') {
  renderRecommendation(result.recommendList);
}

if (result.responseType === 'route') {
  const activeDay = String(result.day);
  renderRoute(result.travelPath[activeDay]);
}
```

---

## 7. 구현 위치

| 역할 | 파일 |
|---|---|
| 최종 응답 스키마 | `schemas/frontend_response.py` |
| 내부 결과 → 프론트 변환 | `application/response/frontend_response_mapper.py` |
| SSE 연결 | `routers/chat.py` |
| 프론트 소비 예시 | `frontend/src/pages/ChatSidebar.jsx` |
| 계약·변환 테스트 | `tests/test_frontend_response.py` |

루트에서 장소를 삭제하고 단일 추천 장소를 원하는 위치에 추가하는 구현은
`docs/FRONTEND_ROUTE_MANUAL_INSERT_GUIDE_NOTION.md`를 참고한다. 루트 편집은
백엔드를 다시 호출하지 않고 프론트 Zustand 상태에서 처리한다.
