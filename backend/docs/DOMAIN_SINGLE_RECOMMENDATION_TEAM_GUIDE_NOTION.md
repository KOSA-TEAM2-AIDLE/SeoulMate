# 카페·숙박·명소 단일 장소 추천 구현 가이드

## 1. 목적

이 문서는 카페, 숙박, 명소 검색을 담당하는 팀원이 자신의 검색 알고리즘을 SeoulMate 백엔드에 연결하기 위한 공통 계약이다.

팀원이 직접 만들어야 하는 것은 **프론트 최종 JSON이 아니라 도메인 후보 검색기**다.

```text
첫 GPT Structured Query
→ 공통 DomainSearchRequest
→ 팀 검색기
→ SearchCandidate 최대 10개
→ 공통 재랭킹·최종 선택
→ 프론트 recommendList 최대 3개
```

식당 검색은 이미 구현되어 있다. 카페·숙박·명소 팀은 같은 공통 인터페이스를 구현하되, 자신의 DB/API 특성에 맞는 근거와 속성을 제공한다.

---

## 2. 구현 대상 파일

| 도메인 | domain 값 | 구현 파일 |
|---|---|---|
| 카페 | `cafe` | `backend/domains/cafe/search_service.py` |
| 숙박 | `accommodation` | `backend/domains/accommodation/search_service.py` |
| 명소·문화시설 | `attraction` | `backend/domains/attraction/search_service.py` |

현재 파일은 `SkeletonDomainSearchService`를 상속하는 스켈레톤이다. 팀원은 이를 실제 서비스로 교체한다.

```python
class CafeSearchService:
    domain = "cafe"
    implemented = True

    async def search(
        self,
        request: DomainSearchRequest,
    ) -> list[SearchCandidate]:
        ...
```

함수 이름과 입력·출력 타입은 임의로 바꾸지 않는다.

---

## 3. 검색기가 받는 입력

공통 입력 모델:

```text
backend/domains/common/models.py
DomainSearchRequest
```

```python
class DomainSearchRequest:
    task_id: str
    domain: str
    language: str
    search_query: str
    themes: list[str]
    location: str | None
    latitude: float | None
    longitude: float | None
    current_location_name: str | None
    radius_km: float | None
    visit_date: date | None
    start_time: str | None
    end_time: str | None
    party_size: int | None
    budget_min_krw: int | None
    budget_max_krw: int | None
    required_features: list[str]
    excluded_features: list[str]
    candidate_count: int
```

### 입력 사용 원칙

- 사용자 원문을 다시 GPT로 파싱하지 않는다.
- `search_query`와 `themes`는 벡터·키워드 검색에 사용한다.
- 지역, 날짜, 시간, 예산, 시설은 구조화된 필드를 우선 사용한다.
- 값이 `None`이면 사용자가 확정하지 않은 조건이다. 임의의 기본 조건을 하드 필터로 만들지 않는다.
- `required_features`는 확인 가능한 데이터가 있을 때만 하드 필터로 사용한다.
- 정보가 없는 것과 조건 불일치를 구분한다.
- `candidate_count`만큼 반환하도록 시도하되, 부적합 후보로 억지로 채우지 않는다.

---

## 4. 검색기가 반환할 공통 후보

모든 팀 검색기는 `list[SearchCandidate]`를 반환한다.

```python
SearchCandidate(
    domain="cafe",
    place_id="CAFE-1024",
    task_id=request.task_id,
    name="카페 이름",
    category="베이커리 카페",
    latitude=37.5665,
    longitude=126.9780,
    base_score=0.82,
    final_score=0.87,
    evidence=[
        "공식 정보에 좌석과 콘센트가 확인됨",
        "조용하다는 리뷰 근거가 반복적으로 확인됨",
    ],
    attributes={...},
    signals={...},
)
```

### 필수 필드

| 필드 | 규칙 |
|---|---|
| `domain` | `cafe`, `accommodation`, `attraction` 중 담당 값 |
| `place_id` | 프론트 상세 API가 사용하는 실제 도메인 ID를 문자열로 전달 |
| `task_id` | `request.task_id`를 그대로 복사 |
| `name` | DB/API에서 확인된 실제 장소명 |
| `category` | 실제 세부 유형. 예: 베이커리 카페, 호텔, 미술관 |
| `base_score` | 도메인 자체 검색 점수 |
| `final_score` | 도메인 필터·재랭킹까지 반영한 최종 점수 |
| `evidence` | 선정 이유에 사용할 수 있는 검증된 짧은 근거 목록 |

### 공통 attributes 키

가능한 경우 다음 키 이름으로 통일한다.

```python
attributes={
    "address": "서울 ...",
    "image": "https://...",
    "rating": 4.6,
    "review_count": 321,
    "sub_category": "베이커리 카페",
    "opening_hours": {...},
    "price_min_krw": 5000,
    "price_max_krw": 12000,
}
```

값이 없으면 필드를 생략하거나 `None`으로 둔다. 빈 문자열, 가짜 평점, 임시 이미지를 넣지 않는다.

### signals 사용 원칙

`signals`에는 내부 점수와 재랭킹 근거를 넣는다.

```python
signals={
    "vector_score": 0.81,
    "keyword_score": 0.74,
    "distance_km": 1.2,
    "open_at_visit": True,
}
```

`signals`의 내부 필드명은 사용자 답변에 그대로 노출하지 않는다.

---

## 5. 카페 팀 구현 요구사항

### 검색 대상

- 카페명과 설명
- 카테고리와 대표 메뉴
- 리뷰 또는 분위기 태그
- 좌석, 콘센트, 와이파이, 주차, 반려동물 등 확인 가능한 시설
- 영업시간
- 위치와 거리

### 권장 attributes

```python
attributes={
    "address": "서울 성동구 ...",
    "image": "https://...",
    "rating": 4.5,
    "review_count": 240,
    "sub_category": "스페셜티 카페",
    "opening_hours": {...},
    "menu_names": ["아메리카노", "크루아상"],
    "has_outlet": True,
    "has_wifi": True,
    "has_parking": False,
    "allows_pets": None,
    "seat_type": ["실내"],
}
```

### 카페 주의사항

- `조용함`, `감성`, `뷰`처럼 주관적인 특성은 리뷰 한 건만으로 확정하지 않는다.
- 공식 설명이나 반복된 리뷰 근거를 `evidence`에 넣는다.
- `has_parking=False`와 정보 없음 `None`을 구분한다.
- 비·더위 같은 날씨는 검색기 내부에서 직접 API를 호출하지 않는다. 공통 MCP 결과를 받은 재랭커에서 사용한다.

---

## 6. 숙박 팀 구현 요구사항

### 검색 대상

- 숙소명과 숙소 유형
- 체크인·체크아웃 날짜
- 인원
- 1박 또는 전체 가격
- 위치
- 객실·편의시설
- 예약 가능 여부

### 권장 attributes

```python
attributes={
    "address": "서울 중구 ...",
    "image": "https://...",
    "rating": 4.7,
    "review_count": 1842,
    "sub_category": "호텔",
    "check_in_time": "15:00",
    "check_out_time": "11:00",
    "nightly_price_krw": 180000,
    "total_price_krw": 360000,
    "amenities": ["와이파이", "조식", "주차"],
    "availability_checked": True,
    "available": True,
}
```

### Booking API 사용 원칙

```text
숙박 DB/RAG에서 후보 검색
→ 가격·위치·시설로 1차 상위 후보 축소
→ 상위 후보에만 Booking 예약 가능 여부 확인
→ final_score 재계산
```

- 모든 숙소에 Booking API를 호출하지 않는다.
- 예약 가능 여부를 확인하지 않았다면 `availability_checked=False`로 둔다.
- 확인하지 않은 숙소를 예약 가능하다고 표시하지 않는다.
- 가격의 기준 날짜, 인원, 세금 포함 여부를 내부 근거에 보존한다.
- `place_id`는 프론트 상세 API가 사용하는 숙박 ID다. Booking의 임시 검색 결과 ID와 혼동하지 않는다.

---

## 7. 명소·문화시설 팀 구현 요구사항

### 검색 대상

- 명소명과 시설 유형
- 전시·행사 기간
- 방문 날짜의 운영 여부
- 운영시간과 휴관일
- 실내·야외
- 입장료와 예약 필요 여부
- 위치와 이동 거리

### 권장 attributes

```python
attributes={
    "address": "서울 종로구 ...",
    "image": "https://...",
    "rating": 4.6,
    "review_count": 820,
    "sub_category": "미술관",
    "opening_hours": {...},
    "closed_days": ["월요일"],
    "indoor_outdoor": "indoor",
    "admission_fee_krw": 15000,
    "reservation_required": False,
    "event_start_date": "2026-07-01",
    "event_end_date": "2026-08-31",
}
```

### 명소 주의사항

- 방문 날짜에 종료된 전시·행사를 반환하지 않는다.
- 운영시간 정보 없음과 휴관을 구분한다.
- 실내·야외 정보가 없으면 날씨 적합성을 추측하지 않는다.
- 혼잡도 MCP가 연결되면 검색기 자체 점수를 덮어쓰지 않고 보조 신호로 반영한다.

---

## 8. 후보 개수와 최종 선택

단일 장소 추천의 제품 정책은 다음과 같다.

```text
팀 검색기 반환: 최대 10개 후보
공통 검증·재랭킹: 순위와 근거 정리
최종 선택: 최대 3개
프론트 표시: recommendList 최대 3개
```

팀 검색기가 처음부터 3개만 반환하면 후속 검증에서 부적합 후보를 제거했을 때 대체 후보가 없다. 가능하면 `request.candidate_count`만큼 반환한다.

후보가 1~2개뿐이라면 가짜 후보로 3개를 채우지 않는다. 실제 후보 수만 반환한다.

---

## 9. 프론트 최종 응답

팀 검색기는 이 JSON을 직접 만들지 않는다. 공통 응답 매퍼가 최종 후보를 다음 구조로 변환한다.

```json
{
  "responseType": "recommendation",
  "day": null,
  "allDay": null,
  "travelPath": null,
  "recommendList": [
    {
      "id": "CAFE-1024",
      "name": "카페 이름",
      "category": "카페",
      "subCategory": "스페셜티 카페",
      "address": "서울 성동구 ...",
      "lat": 37.5665,
      "lng": 126.9780,
      "rating": "4.5",
      "reviews": "240",
      "time": null,
      "image": "https://...",
      "selectionReason": "조용한 분위기와 요청한 위치 조건이 확인된 카페입니다."
    }
  ]
}
```

### 최종 응답 필드 규칙

| 필드 | 책임 |
|---|---|
| `id` | 팀 검색기의 실제 `place_id` 복사 |
| `name` | DB/API 장소명 복사 |
| `category` | 공통 매퍼가 카페·숙소·관광지로 변환 |
| `subCategory` | 팀이 제공한 실제 세부 유형 |
| `address`, `rating`, `reviews`, `image`, 좌표 | 팀 데이터에서만 복사 |
| `selectionReason` | 최종 선택기가 후보의 evidence를 근거로 생성 |
| `time` | 단일 추천에서는 일반적으로 `null`; 루트에 배치될 때 방문시간 사용 |

GPT가 생성해도 되는 값은 원칙적으로 `selectionReason`과 답변 문장뿐이다. ID, 장소명, 주소, 평점, 리뷰 수, 이미지, 좌표를 생성하면 안 된다.

---

## 10. 현재 백엔드 연결 시 반드시 확인할 점

현재 `/chat`의 비식당 도메인은 `mock_places_for_task()`를 사용하는 과도기 코드가 남아 있다. 팀 검색기 파일만 구현하면 자동으로 실제 응답으로 바뀌지 않는다.

백엔드 통합 담당자는 다음 작업을 함께 해야 한다.

1. 팀 검색기의 `implemented=True` 확인
2. `build_default_domain_registry()`에서 해당 서비스 등록 확인
3. `/chat`의 비식당 `mock_places_for_task()` 호출을 `RecommendationOrchestrator` 또는 Registry 검색 호출로 교체
4. `SearchCandidate`를 내부 `Place`로 변환하는 공통 매퍼 연결
5. Task별 후보 10개와 최종 3개가 섞이지 않는지 확인
6. `task_id`, `domain`, `place_id`가 끝까지 유지되는지 확인
7. 프론트 `recommendList[].id`가 상세 API에서 실제 조회되는지 확인

Mock 제거 전에는 실제 팀 검색기와 임시 후보가 동시에 노출되지 않도록 한다.

---

## 11. 빈 결과와 장애 처리

### 조건에 맞는 장소가 없음

```python
return []
```

비슷하지만 조건을 위반하는 장소를 억지로 반환하지 않는다.

### 일부 상세 정보가 없음

후보는 반환하되 해당 attributes 값을 `None`으로 둔다. GPT가 채우지 않는다.

### DB/API 장애

- 내부 로그에는 도메인, task_id, 실패 원인을 남긴다.
- API 키와 개인정보는 로그에 남기지 않는다.
- 일시 장애와 빈 검색 결과를 구분한다.
- 팀 합의 없이 임시 Mock 후보로 조용히 대체하지 않는다.

---

## 12. 팀별 필수 테스트

각 팀은 최소 다음 테스트를 작성한다.

- [ ] `request.domain`이 담당 도메인이 아니면 오류 처리
- [ ] `request.task_id`가 모든 후보에 그대로 보존됨
- [ ] `place_id`가 비어 있으면 후보 생성 실패
- [ ] 같은 `place_id` 중복 제거
- [ ] 위치·반경 필터 검증
- [ ] 방문 날짜와 영업/운영 기간 검증
- [ ] 예산 최소·최대 검증
- [ ] required/excluded feature 검증
- [ ] 정보 없음과 `False` 구분
- [ ] `candidate_count` 상한 준수
- [ ] 점수 내림차순 정렬
- [ ] 빈 결과가 정상적으로 `[]` 반환
- [ ] 한국어 질문과 영어 질문 모두 테스트
- [ ] 실제 ID로 상세 API 호출 성공
- [ ] 최종 recommendList가 최대 3개
- [ ] GPT가 사실 필드를 생성하지 않음

### 도메인 추가 테스트

카페:

- [ ] 조용함·분위기 같은 주관 태그의 근거 확인
- [ ] 콘센트·주차·반려동물의 `True/False/None` 구분

숙박:

- [ ] 체크인·체크아웃 날짜와 인원 전달
- [ ] 가격 기준과 Booking 확인 여부 구분
- [ ] 상위 후보에만 예약 가능 여부 조회

명소:

- [ ] 방문일에 종료된 행사 제외
- [ ] 휴관일·운영시간 확인
- [ ] 실내외 정보가 없을 때 날씨 적합성 추측 금지

---

## 13. 완료 조건

다음 조건을 모두 만족하면 도메인 단일 추천 구현이 완료된 것이다.

1. 스켈레톤을 실제 `DomainSearchService`로 교체했다.
2. `implemented=True`다.
3. 공통 `DomainSearchRequest`만 사용하며 사용자 원문을 다시 파싱하지 않는다.
4. 최대 10개의 검증된 `SearchCandidate`를 반환한다.
5. 모든 후보에 실제 `place_id`, `task_id`, domain이 있다.
6. 근거 없는 상세 정보와 후보를 생성하지 않는다.
7. Registry와 `/chat` 실행 경로에 연결됐다.
8. Mock 후보가 제거됐다.
9. 최종 `recommendList`가 최대 3개다.
10. 프론트가 `id`로 상세 API를 정상 호출할 수 있다.

---

## 14. 팀원에게 전달할 핵심 문장

```text
프론트 JSON을 직접 만들지 말고 DomainSearchRequest를 받아 SearchCandidate 최대 10개를 반환해 주세요.
place_id에는 프론트 상세 API가 사용하는 실제 도메인 ID를 넣고, 확인된 상세 정보와 evidence만 제공해 주세요.
공통 백엔드가 재랭킹과 최종 3개 선택, recommendList 변환을 담당합니다.
```
