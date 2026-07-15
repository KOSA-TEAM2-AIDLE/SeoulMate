# 여행 루트 장소 삭제 및 원하는 위치에 추가하기

## 1. 문서 목적

이 문서는 프론트엔드 팀원이 다음 기능을 구현하기 위한 작업 설명서다.

- 사용자가 여행 루트에서 마음에 들지 않는 장소를 삭제한다.
- 단일 장소 추천 결과에서 새로운 장소를 선택한다.
- 사용자가 새 장소를 추가할 날짜와 순서를 직접 정한다.
- 선택한 장소를 해당 날짜의 지정된 위치에 삽입한다.

이 기능은 프론트엔드의 Zustand 상태만 변경한다. 백엔드 저장, GPT 재호출, RAG 재검색, MCP 재호출은 하지 않는다.

---

## 2. 최종 사용자 흐름

```text
GPT가 생성한 travelPath를 왼쪽 여행 루트에 표시
        ↓
사용자가 마음에 들지 않는 장소 삭제
        ↓
단일 장소 추천에서 원하는 장소 선택
        ↓
"루트에 추가" 클릭
        ↓
추가할 Day 선택
        ↓
추가할 위치 선택
        ↓
Zustand travelPath의 지정된 위치에 삽입
        ↓
왼쪽 여행 루트 화면 즉시 갱신
```

사용자가 장소를 여러 개 삭제해도 문제없다. 삭제 위치를 따로 기억하지 않고, 새 장소를 추가하는 시점의 현재 루트를 보여준 뒤 사용자가 위치를 직접 선택한다.

---

## 3. 이번 작업에서 하지 않는 것

- 수정된 루트를 백엔드 DB에 저장하지 않는다.
- 장소 삭제 사실을 백엔드에 전달하지 않는다.
- 폐기된 백엔드 루트 수정 API를 호출하지 않는다.
- GPT에게 루트를 다시 만들도록 요청하지 않는다.
- 거리나 이동시간을 계산하여 루트를 자동 최적화하지 않는다.
- `localStorage`를 사용하지 않는다.
- 로그인이나 사용자 식별 기능을 추가하지 않는다.

따라서 새로고침하면 현재 편집 중인 루트가 사라질 수 있다. 현재 MVP에서는 이를 허용한다.

---

## 4. 현재 코드에서 사용하는 상태

Zustand 스토어:

```text
frontend/src/stores/useTravelStore.js
```

주요 상태 구조:

```js
{
  travelPath: {
    1: [placeA, placeB, placeC],
    2: [placeD, placeE]
  },
  day: 1,
  all_day: 2
}
```

- `travelPath`: 일차별 장소 배열
- `day`: 현재 선택된 일차
- `all_day`: 전체 여행 일수
- 배열의 순서가 화면의 방문 순서다.

예를 들어 다음 상태에서:

```js
travelPath: {
  1: [경복궁, 광장시장, 청계천]
}
```

`광장시장`은 Day 1의 두 번째 장소다.

---

## 5. 수정할 파일

### 필수 수정

```text
frontend/src/stores/useTravelStore.js
frontend/src/components/sidebar/PlaceRecommendTab.jsx
```

### 선택 사항

위치 선택 UI를 별도 컴포넌트로 분리하려면 다음 파일을 새로 만들 수 있다.

```text
frontend/src/components/sidebar/RouteInsertDialog.jsx
```

규모가 작으면 `PlaceRecommendTab.jsx` 안에서 팝업을 직접 구현해도 된다.

현재 삭제 버튼이 있는 다음 파일은 원칙적으로 변경할 필요가 없다.

```text
frontend/src/components/sidebar/TravelRouteTab.jsx
```

---

## 6. Zustand에 지정 위치 삽입 함수 추가

`useTravelStore.js`에 `insertPathItem`을 추가한다.

```js
insertPathItem: (day, index, item) => {
  let isAdded = false;

  set((state) => {
    const targetDay = Number(day);
    const currentPath = state.travelPath[targetDay] || [];

    // 같은 날짜에 동일한 장소가 있으면 중복 추가하지 않는다.
    const alreadyExists = currentPath.some(
      (place) => String(place.id) === String(item.id),
    );

    if (alreadyExists) {
      return state;
    }

    const nextPath = [...currentPath];

    // 잘못된 index가 들어와도 배열 범위를 벗어나지 않도록 보정한다.
    const numericIndex = Number(index);
    const safeIndex = Number.isFinite(numericIndex)
      ? Math.max(0, Math.min(numericIndex, nextPath.length))
      : nextPath.length;

    nextPath.splice(safeIndex, 0, item);
    isAdded = true;

    return {
      travelPath: {
        ...state.travelPath,
        [targetDay]: nextPath,
      },
    };
  });

  return isAdded;
},
```

기존 `addPathItem(day, item)`은 삭제하지 않는다. 다른 화면에서 마지막 위치 추가 용도로 사용할 수 있다.

### 인덱스 규칙

| 사용자에게 보이는 위치 | 전달할 index |
|---|---:|
| 맨 앞 | `0` |
| 첫 번째 장소 다음 | `1` |
| 두 번째 장소 다음 | `2` |
| 세 번째 장소 다음 | `3` |
| 맨 마지막 | `currentPath.length` |

React 배열은 0부터 시작하지만, 사용자에게는 `index`라는 표현을 노출하지 않는다.

---

## 7. 추천 장소 클릭 동작 변경

현재 `PlaceRecommendTab.jsx`에서는 추천 장소 카드를 클릭하면 다음 함수가 즉시 실행된다.

```js
addPathItem(currentSelectedDay, place);
```

이 동작을 다음과 같이 변경한다.

```text
추천 카드 클릭 또는 "루트에 추가" 버튼 클릭
→ 선택한 장소를 selectedPlace에 저장
→ 위치 선택 팝업 열기
```

권장 로컬 상태:

```js
const [selectedPlace, setSelectedPlace] = useState(null);
const [selectedDay, setSelectedDay] = useState(currentSelectedDay);
const [selectedIndex, setSelectedIndex] = useState(null);
```

스토어에서 다음 값을 읽는다.

```js
const allDay = useTravelStore((state) => state.all_day);
const travelPath = useTravelStore((state) => state.travelPath);
const insertPathItem = useTravelStore((state) => state.insertPathItem);
```

추천 카드 전체를 클릭 대상으로 사용해도 되지만, 오동작을 줄이려면 카드 안에 명시적인 버튼을 두는 것을 권장한다.

```jsx
<button
  type="button"
  onClick={(event) => {
    event.stopPropagation();
    setSelectedPlace(place);
    setSelectedDay(currentSelectedDay);
    setSelectedIndex(null);
  }}
>
  루트에 추가
</button>
```

---

## 8. 날짜 선택 UI

팝업에서 `all_day`만큼 Day 버튼을 표시한다.

```jsx
{Array.from({ length: allDay }, (_, index) => index + 1).map((dayNumber) => (
  <button
    key={dayNumber}
    type="button"
    onClick={() => {
      setSelectedDay(dayNumber);
      setSelectedIndex(null);
    }}
  >
    Day {dayNumber}
  </button>
))}
```

날짜가 바뀌면 선택 가능한 위치도 달라지므로 `selectedIndex`를 반드시 초기화한다.

선택된 날짜의 현재 루트는 다음과 같이 구한다.

```js
const selectedDayPath = travelPath[selectedDay] || [];
```

---

## 9. 삽입 위치 선택 UI

권장 표시 방식:

```text
추가 위치

( ) 맨 앞
( ) 1. 경복궁 다음
( ) 2. 광장시장 다음
( ) 3. 청계천 다음
```

구현 예시:

```jsx
<label>
  <input
    type="radio"
    name="insert-position"
    checked={selectedIndex === 0}
    onChange={() => setSelectedIndex(0)}
  />
  맨 앞
</label>

{selectedDayPath.map((place, index) => (
  <label key={`${place.id}-${index}`}>
    <input
      type="radio"
      name="insert-position"
      checked={selectedIndex === index + 1}
      onChange={() => setSelectedIndex(index + 1)}
    />
    {index + 1}. {place.name} 다음
  </label>
))}
```

현재 날짜의 루트가 비어 있다면 `맨 앞`만 표시하고 `selectedIndex`를 `0`으로 설정한다.

```js
const effectiveIndex = selectedDayPath.length === 0 ? 0 : selectedIndex;
```

---

## 10. 추가 확정 처리

사용자가 날짜와 위치를 선택한 뒤 `추가` 버튼을 누르면 다음 함수를 실행한다.

```js
function handleConfirmInsert() {
  if (!selectedPlace || selectedIndex === null) {
    showToast('추가할 날짜와 위치를 선택해주세요.');
    return;
  }

  const isAdded = insertPathItem(
    selectedDay,
    selectedIndex,
    selectedPlace,
  );

  if (!isAdded) {
    showToast(`'${selectedPlace.name}'은(는) 이미 해당 일차 루트에 존재합니다.`);
    return;
  }

  showToast(
    `Day ${selectedDay}의 ${selectedIndex + 1}번째 위치에 '${selectedPlace.name}'이(가) 추가되었습니다.`,
  );

  setSelectedPlace(null);
  setSelectedIndex(null);
}
```

주의: `selectedIndex`는 삽입 전 배열 기준이다. 삽입 후 사용자가 보는 순번은 `selectedIndex + 1`이다.

취소 버튼은 다음 상태만 초기화하면 된다.

```js
function handleCancelInsert() {
  setSelectedPlace(null);
  setSelectedIndex(null);
}
```

---

## 11. 여러 장소를 삭제한 경우

별도 처리가 필요하지 않다.

예시:

```text
기존
1. 경복궁
2. 광장시장
3. 청계천
4. 홍대 카페
5. 숙소

2번과 4번 삭제 후
1. 경복궁
2. 청계천
3. 숙소
```

사용자가 새 식당을 추가할 때 현재 목록을 기준으로 `경복궁 다음`을 선택하면 두 번째에 들어간다.

```text
1. 경복궁
2. 새 식당
3. 청계천
4. 숙소
```

다음 카페를 추가할 때 `청계천 다음`을 선택하면 네 번째에 들어간다.

```text
1. 경복궁
2. 새 식당
3. 청계천
4. 새 카페
5. 숙소
```

삭제했던 원래 위치를 저장할 필요가 없다. 사용자가 추가 시점의 현재 경로를 보고 정확한 위치를 결정한다.

---

## 12. 필수 예외 처리

### 동일 장소 중복

같은 날짜에 같은 `id`의 장소가 이미 있다면 추가하지 않는다.

```text
'장소명'은(는) 이미 해당 일차 루트에 존재합니다.
```

다른 날짜에는 같은 장소를 추가할 수 있도록 현재 날짜 배열 안에서만 중복 검사한다.

### 잘못된 위치 값

`index < 0`이면 맨 앞으로 보정한다. 배열 길이보다 크면 맨 마지막으로 보정한다.

### 빈 날짜

해당 Day에 장소가 하나도 없으면 `맨 앞`만 제공하고 `index = 0`을 사용한다.

### 팝업을 연 상태에서 루트 변경

팝업이 열린 상태에서 다른 동작으로 루트가 바뀔 수 있으므로, 최종 삽입 시 `insertPathItem` 내부에서 index를 한 번 더 보정한다.

### ID 타입 차이

백엔드/API에 따라 `id`가 숫자 또는 문자열일 수 있으므로 중복 검사는 `String(id)`로 비교한다.

### 삽입 버튼 중복 클릭

추가 처리 중 버튼을 잠시 비활성화하거나, 첫 성공 직후 팝업을 닫아 연속 클릭을 방지한다. Zustand의 중복 검사도 마지막 방어선으로 유지한다.

---

## 13. GPT 및 백엔드 응답 구조

이번 기능 때문에 GPT 최종 응답 JSON을 변경하지 않는다.

루트 응답:

```json
{
  "responseType": "route",
  "day": 1,
  "allDay": 2,
  "travelPath": {
    "1": [],
    "2": []
  },
  "recommendList": null
}
```

단일 추천 응답:

```json
{
  "responseType": "recommendation",
  "day": null,
  "allDay": null,
  "travelPath": null,
  "recommendList": []
}
```

단일 추천의 장소 객체를 그대로 `insertPathItem`에 전달한다. 프론트에서 장소 이름, 주소, 평점, 이미지 등을 새로 생성하지 않는다.

`id`는 상세 API 호출에 사용하는 실제 도메인 ID여야 한다.

---

## 14. 화면 동작 기준

### 추가 전

```text
Day 1
1. 경복궁
2. 청계천
3. 숙소
```

단일 추천의 `새 식당`에서 `루트에 추가`를 누른 뒤 다음을 선택한다.

```text
날짜: Day 1
위치: 경복궁 다음
```

### 추가 후

```text
Day 1
1. 경복궁
2. 새 식당
3. 청계천
4. 숙소
```

화면 번호는 `TravelRouteTab.jsx`에서 배열 순서에 따라 자동으로 다시 표시된다.

---

## 15. 테스트 체크리스트

### 기본 삽입

- [ ] Day 1 맨 앞에 장소를 추가할 수 있다.
- [ ] Day 1 중간에 장소를 추가할 수 있다.
- [ ] Day 1 맨 마지막에 장소를 추가할 수 있다.
- [ ] 장소 추가 후 화면 번호가 올바르게 다시 표시된다.

### 여러 날짜

- [ ] Day 2를 선택하면 Day 2의 장소 목록으로 위치 선택지가 바뀐다.
- [ ] Day 2에 추가해도 Day 1의 배열은 변경되지 않는다.
- [ ] Day를 변경하면 이전에 선택한 위치가 초기화된다.

### 삭제 후 추가

- [ ] 장소 한 개를 삭제한 뒤 원하는 위치에 새 장소를 추가할 수 있다.
- [ ] 장소 두 개 이상을 삭제한 뒤 각각 원하는 위치에 추가할 수 있다.
- [ ] 삭제한 원래 위치가 아니라 사용자가 선택한 현재 위치에 삽입된다.

### 예외 상황

- [ ] 같은 날짜에 동일한 장소를 두 번 추가할 수 없다.
- [ ] 동일 장소를 다른 날짜에는 추가할 수 있다.
- [ ] 빈 Day에는 장소가 첫 번째로 추가된다.
- [ ] 위치를 선택하지 않으면 추가되지 않고 안내 메시지가 표시된다.
- [ ] 팝업 취소 시 루트가 변경되지 않는다.
- [ ] 빠르게 추가 버튼을 여러 번 눌러도 중복되지 않는다.

---

## 16. 완료 조건

다음 조건을 모두 만족하면 구현 완료다.

1. 기존 삭제 버튼이 정상 작동한다.
2. 추천 장소 클릭 시 즉시 마지막에 추가되지 않는다.
3. 사용자가 Day와 삽입 위치를 선택할 수 있다.
4. 선택한 위치에 장소가 정확하게 삽입된다.
5. 여러 장소 삭제 후에도 정상 작동한다.
6. 같은 날짜의 동일 장소 중복 추가가 차단된다.
7. 백엔드 추가 호출 없이 Zustand 상태만 변경된다.
8. GPT와 백엔드의 최종 응답 JSON은 변경하지 않는다.

---

## 17. 핵심 요약

프론트엔드에서 구현할 핵심은 하나다.

```text
기존: addPathItem(day, item) → 무조건 마지막에 추가

변경: insertPathItem(day, index, item) → 사용자가 선택한 위치에 추가
```

삭제된 위치를 기억하거나 자동으로 추론하지 않는다. 사용자가 장소를 추가할 때 현재 루트를 보고 Day와 위치를 직접 선택한다. 이 방식이 여러 장소 삭제에도 가장 명확하며, 백엔드 저장 없이 현재 Zustand 구조만으로 구현할 수 있다.
