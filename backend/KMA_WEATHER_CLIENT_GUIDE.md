# 기상청 공용 날씨 클라이언트 사용 설명서

대상 파일: `kma_weather_client.py`

이 파일은 숙박·카페·식당 등 여러 서비스에서 공통으로 사용할 수 있는 독립형 기상청 API 클라이언트다. SeoulMate의 RAG, 데이터베이스, 웹 프레임워크에는 의존하지 않으며 Python 표준 라이브러리만 사용한다.

## 1. 파일 배치

사용할 프로젝트 안에 다음과 같이 파일을 복사한다.

```text
my_backend/
├─ app.py
└─ kma_weather_client.py
```

별도 패키지 설치는 필요하지 않다. Python 3.10 이상 사용을 권장한다.

## 2. 기상청 API 키 설정

공공데이터포털에서 발급받은 기상청 API의 **일반 인증키(Decoding)** 값을 `KMA_API_KEY` 환경변수로 설정한다.

### Windows PowerShell — 현재 터미널에서만 설정

```powershell
$env:KMA_API_KEY="발급받은_DECODING_인증키"
```

### Windows — 사용자 환경변수로 영구 설정

```powershell
[Environment]::SetEnvironmentVariable(
    "KMA_API_KEY",
    "발급받은_DECODING_인증키",
    "User"
)
```

영구 설정 후에는 실행 중인 터미널, IDE, 주피터 커널을 완전히 종료한 다음 다시 실행해야 한다.

### macOS/Linux

```bash
export KMA_API_KEY="발급받은_DECODING_인증키"
```

API 키를 소스 코드나 Git 저장소에 직접 넣지 않는다.

## 3. 가장 간단한 사용법

```python
from kma_weather_client import KmaWeatherClient

weather_client = KmaWeatherClient()

weather = weather_client.get_weather(
    lat=37.5665,
    lng=126.9780,
)

print(weather)
```

질문을 전달하지 않으면 해당 위치의 현재 초단기실황을 조회한다.

## 4. 방문 시각을 반영한 예보 조회

`query`에 날짜와 시간 표현을 넣으면 방문 예정 시각의 단기예보를 조회한다.

```python
weather = weather_client.get_weather(
    lat=37.5665,
    lng=126.9780,
    query="내일 저녁에 가기 좋은 카페",
)
```

지원하는 주요 표현은 다음과 같다.

| 구분 | 지원 예시 | 적용 시각 |
|---|---|---:|
| 날짜 | 오늘, 내일, 모레, 글피, 그글피 | 해당 날짜 |
| 아침 | 내일 아침 | 09:00 |
| 점심 | 오늘 점심 | 12:00 |
| 오후 | 내일 오후 | 15:00 |
| 저녁 | 내일 저녁 | 19:00 |
| 밤 | 오늘 밤 | 21:00 |
| 새벽 | 내일 새벽 | 06:00 |
| 명시적 시간 | 내일 오후 3시 30분, 오늘 18시 | 지정 시각 |
| 영어 | tomorrow evening, in 3 days, today at 3:30 p.m. | 해석된 시각 |

날짜 표현 없이 `"저녁에 좋은 카페"`처럼 입력하면 현재 날씨를 조회한다. 미래 예보가 필요하면 `오늘`, `내일`, `모레`, `글피`, `그글피` 중 하나를 함께 넣는 것이 안전하다.

이미 지나간 오늘의 시각을 지정하면 과거 예보를 찾는 대신 현재 실황을 반환한다.

단기예보는 오늘부터 최대 4일 뒤까지만 자연어로 해석한다. 기상청 응답에 해당 시각의 예보가 실제로 없으면 가장 마지막 예보를 대신 사용하지 않고 `available=False`를 반환한다. 5일 이후 일정은 별도의 기상청 중기예보 API를 사용해야 한다.

## 5. 한국어·영어 지원

기본 언어는 한국어다. 영어 서비스에서는 `language="en"`을 전달한다.

```python
weather_en = weather_client.get_weather(
    lat=37.5665,
    lng=126.9780,
    query="a cafe to visit tomorrow evening",
    language="en",
)

print(weather_en["target_label"])      # Tomorrow evening
print(weather_en["condition_label"])   # Rain
print(weather_en["summary"])           # Tomorrow evening: Rain, 27°C.
```

영어로 지원하는 주요 시간 표현은 다음과 같다.

| 표현 | 적용 시각 |
|---|---:|
| `today`, `tomorrow`, `day after tomorrow` | 오늘~모레 |
| `in 2 days`, `in 3 days`, `in 4 days` | 2~4일 뒤 |
| `morning`, `breakfast` | 09:00 |
| `noon`, `lunch` | 12:00 |
| `afternoon` | 15:00 |
| `evening`, `dinner`, `tonight` | 19:00 |
| `night` | 21:00 |
| `dawn`, `early morning` | 06:00 |
| `3pm`, `3 p.m.`, `3:30 pm`, `15:00` | 지정 시각 |
| `this morning`, `this afternoon`, `this evening`, `this night` | 오늘의 해당 시각 |
| `evening around 7`, `morning at seven`, `half past seven` | 문맥에 따라 해석 |

`at 7`처럼 오전·오후를 판단할 근거가 없는 표현은 임의로 해석하지 않는다. `at 7pm`, `morning at 7`, `evening around 7`처럼 시간대를 함께 입력해야 한다. `13pm`, `25:00`, `오후 15시`처럼 잘못된 시간은 기본 시각으로 바꾸지 않고 `available=False`와 `source="weather-query-parser"`를 반환한다.

`condition`, `sky`, `feels_like` 같은 판정용 필드는 언어와 관계없이 항상 영어 코드로 유지된다. 따라서 팀별 재랭킹 코드는 번역할 필요 없이 동일하게 사용할 수 있다.

```python
if weather_en["condition"] == "rain":
    # 한국어 응답과 동일한 재랭킹 규칙 적용
    pass
```

언어별로 달라지는 필드는 다음과 같다.

| 필드 | 설명 |
|---|---|
| `language` | `ko` 또는 `en` |
| `target_label` | 방문 시각의 한국어/영어 표현 |
| `condition_label` | 강수 상태의 표시용 번역 |
| `sky_label` | 하늘 상태의 표시용 번역 |
| `feels_like_label` | 기온 구간의 표시용 번역 |
| `summary` | GPT 또는 화면에 전달할 짧은 날씨 문장 |

지원하지 않는 언어를 넘기면 `ValueError`가 발생한다.

## 6. 현재 날씨만 명시적으로 조회

```python
current = weather_client.get_current(
    lat=37.5665,
    lng=126.9780,
)
```

내부적으로 기상청 `getUltraSrtNcst` 초단기실황 API를 사용한다.

## 7. 특정 미래 시각을 직접 조회

자연어 질문을 사용하지 않고 목표 시각을 직접 지정할 수도 있다.

```python
from datetime import datetime
from kma_weather_client import KmaWeatherClient, KST

weather_client = KmaWeatherClient()

forecast = weather_client.get_forecast(
    lat=37.5665,
    lng=126.9780,
    target_at=datetime(2026, 7, 15, 19, 0, tzinfo=KST),
    target_label="내일 저녁",
)
```

내부적으로 기상청 `getVilageFcst` 단기예보 API를 사용하며, 목표 시각과 가장 가까운 1시간 예보를 반환한다.

## 8. 정상 응답 구조

```python
{
    "available": True,
    "is_forecast": True,
    "target_label": "내일 19시 30분",
    "requested_for": "2026-07-15T19:30:00+09:00",
    "forecast_for": "2026-07-15T20:00:00+09:00",
    "forecast_offset_minutes": 30,
    "location": {
        "lat": 37.5665,
        "lng": 126.978,
        "nx": 60,
        "ny": 127
    },
    "temperature_c": 27.0,
    "humidity_pct": 80.0,
    "precipitation_probability_pct": 60.0,
    "rainfall_mm": 1.0,
    "wind_speed_mps": 5.2,
    "condition": "rain",
    "condition_label": "비",
    "sky": "cloudy",
    "sky_label": "흐림",
    "feels_like": "mild",
    "feels_like_label": "온화함",
    "language": "ko",
    "summary": "내일 19시 30분: 비, 27°C입니다.",
    "source": "KMA-vilage-forecast"
}
```

### 주요 필드

| 필드 | 의미 |
|---|---|
| `available` | 날씨를 정상적으로 가져왔는지 여부 |
| `is_forecast` | 미래 예보이면 `True`, 현재 실황이면 `False` |
| `target_label` | 사람이 읽기 쉬운 방문 시각 |
| `requested_for` | 사용자가 요청한 정확한 방문 시각 |
| `forecast_for` | 실제 적용된 날씨 시각(ISO 8601) |
| `forecast_offset_minutes` | 실제 예보 시각과 요청 시각의 차이(분) |
| `temperature_c` | 기온(℃) |
| `humidity_pct` | 습도(%) |
| `precipitation_probability_pct` | 강수확률(%), 현재 실황에서는 `None` |
| `rainfall_mm` | 1시간 강수량(mm) |
| `wind_speed_mps` | 풍속(m/s) |
| `condition` | `clear`, `rain`, `snow` 중 하나 |
| `sky` | `clear`, `mostly_cloudy`, `cloudy` 또는 `None` |
| `feels_like` | 단순 기온 구간인 `hot`, `mild`, `cold` |
| `source` | 사용한 기상청 API 종류 |

`feels_like`는 체감온도 공식으로 계산한 값이 아니라 추천 규칙에 쓰기 위한 단순 기온 구간이다.

## 9. API 오류 처리

API 키 누락, 네트워크 장애, 기상청 타임아웃 등이 발생해도 일반 호출에서는 예외를 외부로 던지지 않고 다음 형태로 반환한다.

```python
{
    "available": False,
    "location": {
        "lat": 37.5665,
        "lng": 126.978,
        "nx": 60,
        "ny": 127
    },
    "source": "KMA-ultra-short-observation",
    "error": "오류 내용"
}
```

따라서 사용하는 쪽에서는 반드시 `available`을 확인한다.

```python
weather = weather_client.get_weather(37.5665, 126.9780, "내일 저녁")

if not weather["available"]:
    # 날씨 없이 기존 추천 로직을 그대로 실행한다.
    weather = None
```

날씨 조회 실패 때문에 숙박·카페·식당 검색 전체가 실패하도록 만들지 않는 것이 권장된다.

## 10. 서비스별 활용 예시

### 카페

```python
weather = weather_client.get_weather(cafe_lat, cafe_lng, user_query)

if weather["available"]:
    if weather["condition"] in {"rain", "snow"}:
        # 야외석 중심 카페 감점, 주차 가능 카페 가점
        pass
    elif weather["condition"] == "clear" and weather["temperature_c"] < 28:
        # 테라스·루프탑 카페 소폭 가점
        pass
```

### 숙박

```python
weather = weather_client.get_weather(hotel_lat, hotel_lng, user_query)

if weather["available"]:
    if weather["condition"] in {"rain", "snow"}:
        # 실내 부대시설, 주차, 역 접근성이 좋은 숙소 가점
        pass
    if weather["wind_speed_mps"] is not None and weather["wind_speed_mps"] >= 7:
        # 야외 수영장·루프탑 의존도가 높은 숙소 감점
        pass
```

### 식당

```python
weather = weather_client.get_weather(restaurant_lat, restaurant_lng, user_query)

if weather["available"]:
    temperature = weather["temperature_c"]
    if temperature <= 8:
        # 탕·찌개·전골 등 따뜻한 메뉴 가점
        pass
    elif temperature >= 28:
        # 냉면·콩국수·빙수 등 시원한 메뉴 가점
        pass
```

날씨는 필터보다는 작은 가점·감점 신호로 사용하는 것이 안전하다. 정보가 없거나 API 조회가 실패한 경우 기존 점수를 그대로 유지한다.

## 11. 타임아웃·재시도·캐시 설정

```python
weather_client = KmaWeatherClient(
    cache_ttl_seconds=600,  # 동일 조회 결과를 10분간 캐시
    timeout_seconds=15.0,   # API 요청 1회 타임아웃
    max_retries=1,          # 최초 실패 후 1회 재시도
)
```

트래픽이 많은 서버에서는 애플리케이션 인스턴스마다 객체를 새로 만들지 말고 하나를 재사용해야 메모리 캐시가 작동한다.

```python
# 모듈 전역에서 한 번 생성
weather_client = KmaWeatherClient()

def recommend_places(lat, lng, query):
    weather = weather_client.get_weather(lat, lng, query)
    # 추천 로직 실행
```

여러 서버 인스턴스가 동일 캐시를 공유해야 한다면 이 파일의 메모리 캐시 대신 Redis 또는 공용 Weather REST API를 고려한다.

## 12. API 키를 직접 전달해야 하는 경우

환경변수 사용이 어려운 테스트 환경에서는 생성자에 직접 전달할 수 있다.

```python
weather_client = KmaWeatherClient(api_key="테스트용_API_KEY")
```

운영 코드에서는 환경변수를 사용하는 것이 권장된다.

## 13. 운영 권장 흐름

```text
사용자 질문
  → 방문 날짜·시간 해석
  → 장소의 위도·경도로 날씨 조회
  → available 확인
  → 날씨를 보조 신호로 후보 점수 조정
  → 최종 추천 및 날씨 근거 표시
```

현재 단계에서는 MCP 서버가 필요하지 않다. 각 서비스가 같은 Python 환경에 있다면 이 파일을 직접 사용하고, 서로 다른 서버에 배포된다면 이후 공용 Weather REST API로 감싸는 방식을 권장한다. GPT가 날씨 도구를 자율적으로 선택해 호출해야 할 때만 REST API 앞에 MCP 계층을 추가한다.
