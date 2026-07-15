"""숙박·카페·식당에서 공통으로 쓰는 독립형 기상청 날씨 클라이언트.

외부 패키지와 SeoulMate 내부 모듈에 의존하지 않고 Python 표준 라이브러리만 사용한다.
공공데이터포털에서 발급한 일반 인증키(Decoding)를 ``KMA_API_KEY`` 환경변수에 둔다.

사용 예시::

    from kma_weather_client import KmaWeatherClient

    client = KmaWeatherClient()

    # 시간 표현이 없으면 현재 초단기실황
    current = client.get_weather(37.5665, 126.9780)

    # 질의에 방문 시점이 있으면 해당 시각 단기예보
    dinner = client.get_weather(
        37.5665,
        126.9780,
        query="내일 저녁에 가기 좋은 카페",
    )

    # 영어 질문과 영어 설명
    dinner_en = client.get_weather(
        37.5665,
        126.9780,
        query="a cafe to visit tomorrow evening",
        language="en",
    )

    if dinner["available"]:
        print(dinner["target_label"], dinner["condition"], dinner["temperature_c"])

주요 반환 필드::

    {
        "available": True,
        "is_forecast": True,
        "target_label": "내일 저녁",
        "forecast_for": "2026-07-15T19:00:00+09:00",
        "condition": "rain",           # clear | rain | snow
        "temperature_c": 27.0,
        "humidity_pct": 80.0,
        "precipitation_probability_pct": 60.0,
        "rainfall_mm": 1.0,
        "wind_speed_mps": 5.2,
        "sky": "cloudy",               # clear | mostly_cloudy | cloudy | None
        "feels_like": "mild",          # hot | mild | cold
        "source": "KMA-vilage-forecast"
    }
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


KST = timezone(timedelta(hours=9))
KMA_BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
VILAGE_BASE_HOURS = (2, 5, 8, 11, 14, 17, 20, 23)


class KmaWeatherClient:
    """기상청 초단기실황·단기예보를 공통 날씨 문맥으로 변환한다."""

    def __init__(
        self,
        api_key: str | None = None,
        cache_ttl_seconds: int = 600,
        timeout_seconds: float = 15.0,
        max_retries: int = 1,
    ):
        self.api_key = api_key or os.getenv("KMA_API_KEY")
        self.cache_ttl_seconds = cache_ttl_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self._cache: dict[str, tuple[float, dict]] = {}
        self._cache_lock = threading.Lock()

    @staticmethod
    def latlng_to_grid(lat: float, lng: float) -> tuple[int, int]:
        """위·경도를 기상청 Lambert Conformal Conic 격자로 변환한다."""
        re_value = 6371.00877 / 5.0
        slat1, slat2 = math.radians(30.0), math.radians(60.0)
        olon, olat = math.radians(126.0), math.radians(38.0)
        xo, yo = 43.0, 136.0
        sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
            math.tan(math.pi * 0.25 + slat2 * 0.5)
            / math.tan(math.pi * 0.25 + slat1 * 0.5)
        )
        sf = (math.tan(math.pi * 0.25 + slat1 * 0.5) ** sn * math.cos(slat1)) / sn
        ro = re_value * sf / (math.tan(math.pi * 0.25 + olat * 0.5) ** sn)
        ra = re_value * sf / (
            math.tan(math.pi * 0.25 + math.radians(lat) * 0.5) ** sn
        )
        theta = math.radians(lng) - olon
        if theta > math.pi:
            theta -= 2.0 * math.pi
        if theta < -math.pi:
            theta += 2.0 * math.pi
        theta *= sn
        return int(ra * math.sin(theta) + xo + 0.5), int(ro - ra * math.cos(theta) + yo + 0.5)

    @staticmethod
    def _extract_explicit_time(text: str) -> tuple[int, int] | None:
        """한영 숫자·구어체 시간 표현을 24시간제 `(시, 분)`으로 변환한다."""
        morning_context = any(word in text for word in ("아침", "오전", "morning", "breakfast"))
        evening_context = any(
            word in text
            for word in ("오후", "저녁", "밤", "afternoon", "evening", "dinner", "night", "tonight")
        )

        def validate_minute(value: int) -> int:
            if not 0 <= value <= 59:
                raise ValueError("Minute must be between 0 and 59.")
            return value

        def apply_period(hour: int, period: str | None) -> int:
            if period:
                normalized = re.sub(r"[^ap]", "", period.lower())[:1]
                if not 1 <= hour <= 12:
                    raise ValueError("AM/PM hour must be between 1 and 12.")
                return hour % 12 + (12 if normalized == "p" else 0)
            if not 0 <= hour <= 23:
                raise ValueError("Hour must be between 0 and 23.")
            return hour

        korean = re.search(
            r"(?:(오전|오후)\s*)?(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?",
            text,
        )
        if korean:
            period, hour_text, minute_text = korean.groups()
            hour = int(hour_text)
            minute = validate_minute(int(minute_text or 0))
            if period:
                hour = apply_period(hour, "am" if period == "오전" else "pm")
            else:
                hour = apply_period(hour, None)
                if evening_context and 1 <= hour <= 11:
                    hour += 12
            return hour, minute

        english_ampm = re.search(
            r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?(?![a-z])",
            text,
        )
        if english_ampm:
            hour_text, minute_text, period = english_ampm.groups()
            return (
                apply_period(int(hour_text), period),
                validate_minute(int(minute_text or 0)),
            )

        twenty_four_hour = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
        if twenty_four_hour:
            hour_text, minute_text = twenty_four_hour.groups()
            return apply_period(int(hour_text), None), validate_minute(int(minute_text))

        if re.search(r"\bmidnight\b", text):
            return 0, 0
        if re.search(r"\bnoon\b", text):
            return 12, 0

        number_words = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
        }
        word_pattern = "|".join(number_words)
        conversational = re.search(
            rf"\b(at|around)\s+(\d{{1,2}}|{word_pattern})(?:\s*([ap])\.?\s*m\.?)?\b",
            text,
        )
        half_past = re.search(rf"\bhalf\s+past\s+(\d{{1,2}}|{word_pattern})\b", text)
        match = conversational or half_past
        if match:
            if conversational:
                _, hour_value, period = conversational.groups()
                minute = 0
            else:
                hour_value = half_past.group(1)
                period = None
                minute = 30
            hour = int(hour_value) if hour_value.isdigit() else number_words[hour_value]
            if period:
                return apply_period(hour, period), minute
            if not 1 <= hour <= 12:
                raise ValueError("Conversational hour must be between 1 and 12.")
            if evening_context and hour < 12:
                return hour + 12, minute
            if morning_context:
                return (0 if hour == 12 else hour), minute
            raise ValueError("Ambiguous time: add AM/PM or a morning/evening expression.")

        return None

    @staticmethod
    def resolve_target(
        query: str = "",
        now: datetime | None = None,
        language: str = "ko",
    ) -> dict:
        """오늘부터 그글피까지의 날짜와 시간 표현을 방문시각으로 변환한다."""
        current = (now or datetime.now(KST)).astimezone(KST)
        text = str(query or "").lower()
        language = KmaWeatherClient._normalize_language(language)

        english_days = re.search(r"\bin\s+(\d+)\s+days?\b", text)
        korean_days = re.search(r"\b(\d+)\s*일\s*(?:뒤|후)\b", text)
        relative_days = int((english_days or korean_days).group(1)) if (english_days or korean_days) else None
        if relative_days is not None and relative_days > 4:
            target = (current + timedelta(days=relative_days)).replace(
                hour=19, minute=0, second=0, microsecond=0
            )
            label = f"In {relative_days} days" if language == "en" else f"{relative_days}일 뒤"
            return {
                "target_at": target,
                "label": label,
                "is_future": False,
                "explicit": True,
                "unsupported": True,
            }

        if "그글피" in text:
            day_offset = 4
        elif "글피" in text:
            day_offset = 3
        elif relative_days is not None:
            day_offset = relative_days
        elif "모레" in text or "day after tomorrow" in text:
            day_offset = 2
        elif "내일" in text or "tomorrow" in text:
            day_offset = 1
        elif any(word in text for word in ("오늘", "today", "tonight")) or re.search(
            r"\bthis\s+(?:morning|afternoon|evening|night)\b", text
        ):
            day_offset = 0
        else:
            return {
                "target_at": None,
                "label": "Now" if language == "en" else "현재",
                "is_future": False,
                "explicit": False,
            }

        day_labels = {
            "ko": {0: "오늘", 1: "내일", 2: "모레", 3: "글피", 4: "그글피"},
            "en": {
                0: "Today",
                1: "Tomorrow",
                2: "The day after tomorrow",
                3: "In 3 days",
                4: "In 4 days",
            },
        }
        day_label = day_labels[language][day_offset]

        explicit_time = KmaWeatherClient._extract_explicit_time(text)
        if explicit_time:
            hour, minute = explicit_time
            if language == "en":
                time_label = f"{hour:02d}:{minute:02d}"
            else:
                time_label = f"{hour:02d}시" + (f" {minute:02d}분" if minute else "")
        elif any(word in text for word in ("새벽", "dawn", "early morning")):
            hour, minute, time_label = 6, 0, "early morning" if language == "en" else "새벽"
        elif any(word in text for word in ("아침", "morning", "breakfast")):
            hour, minute, time_label = 9, 0, "morning" if language == "en" else "아침"
        elif any(word in text for word in ("오후", "afternoon")):
            hour, minute, time_label = 15, 0, "afternoon" if language == "en" else "오후"
        elif any(word in text for word in ("점심", "noon", "lunch")):
            hour, minute, time_label = 12, 0, "lunchtime" if language == "en" else "점심"
        elif any(word in text for word in ("밤", "night")) and "tonight" not in text:
            hour, minute, time_label = 21, 0, "night" if language == "en" else "밤"
        else:
            hour, minute = 19, 0
            has_evening = any(
                word in text for word in ("저녁", "evening", "dinner", "tonight")
            )
            if language == "en":
                time_label = "evening" if has_evening else "evening (default 19:00)"
            else:
                time_label = "저녁" if has_evening else "저녁(기본 19시)"

        target = (current + timedelta(days=day_offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if day_offset == 0 and target <= current:
            past_suffix = "using current conditions" if language == "en" else "현재 시각 기준"
            return {
                "target_at": current,
                "label": f"{day_label} {time_label} ({past_suffix})",
                "is_future": False,
                "explicit": True,
            }
        return {
            "target_at": target,
            "label": f"{day_label} {time_label}",
            "is_future": target > current + timedelta(minutes=30),
            "explicit": True,
        }

    def get_weather(
        self,
        lat: float,
        lng: float,
        query: str = "",
        now: datetime | None = None,
        language: str = "ko",
    ) -> dict:
        """질의 시점에 맞는 현재 실황 또는 미래 예보를 반환한다."""
        current = (now or datetime.now(KST)).astimezone(KST)
        language = self._normalize_language(language)
        try:
            target = self.resolve_target(query, current, language=language)
        except ValueError as exc:
            nx, ny = self.latlng_to_grid(lat, lng)
            result = self._error(lat, lng, nx, ny, "weather-query-parser", exc)
            result.update({"is_forecast": False, "target_label": None, "forecast_for": None})
            return self._localize(result, language)
        if target.get("unsupported"):
            nx, ny = self.latlng_to_grid(lat, lng)
            message = (
                "The requested date requires the KMA mid-range forecast API."
                if language == "en"
                else "요청 날짜는 기상청 중기예보 API가 필요한 범위입니다."
            )
            result = self._error(
                lat,
                lng,
                nx,
                ny,
                "KMA-mid-range-forecast-required",
                RuntimeError(message),
            )
            result.update(
                {
                    "is_forecast": True,
                    "target_label": target["label"],
                    "forecast_for": target["target_at"].isoformat(),
                }
            )
            return self._localize(result, language)
        if target["is_future"]:
            return self.get_forecast(
                lat,
                lng,
                target_at=target["target_at"],
                target_label=target["label"],
                now=current,
                language=language,
            )
        context = dict(self.get_current(lat, lng, now=current, language=language))
        context.update(
            {
                "is_forecast": False,
                "target_label": target["label"],
                "forecast_for": current.isoformat(),
            }
        )
        return self._localize(context, language)

    def get_current(
        self,
        lat: float,
        lng: float,
        now: datetime | None = None,
        language: str = "ko",
    ) -> dict:
        """기상청 초단기실황을 조회한다."""
        language = self._normalize_language(language)
        current = (now or datetime.now(KST)).astimezone(KST)
        nx, ny = self.latlng_to_grid(lat, lng)
        base = (current - timedelta(minutes=45)).replace(minute=0, second=0, microsecond=0)
        cache_key = f"current:{nx}:{ny}:{base:%Y%m%d%H}"
        cached = self._cache_get(cache_key)
        if cached:
            return self._localize(dict(cached), language)

        try:
            items = self._request(
                "getUltraSrtNcst",
                {
                    "numOfRows": 100,
                    "base_date": base.strftime("%Y%m%d"),
                    "base_time": base.strftime("%H00"),
                    "nx": nx,
                    "ny": ny,
                },
            )
            if not items:
                base -= timedelta(hours=1)
                items = self._request(
                    "getUltraSrtNcst",
                    {
                        "numOfRows": 100,
                        "base_date": base.strftime("%Y%m%d"),
                        "base_time": base.strftime("%H00"),
                        "nx": nx,
                        "ny": ny,
                    },
                )
            values = {item["category"]: item.get("obsrValue") for item in items}
            temperature = self._required_float(values, "T1H")
            rainfall = self._parse_rainfall(values.get("RN1"))
            pty = int(float(values.get("PTY", 0)))
            result = {
                "available": True,
                "is_forecast": False,
                "location": {"lat": lat, "lng": lng, "nx": nx, "ny": ny},
                "temperature_c": temperature,
                "humidity_pct": self._float_or_none(values.get("REH")),
                "precipitation_probability_pct": None,
                "rainfall_mm": rainfall,
                "wind_speed_mps": self._float_or_none(values.get("WSD")),
                "condition": self._condition(pty, rainfall),
                "sky": None,
                "feels_like": self._feels_like(temperature),
                "observed_at": base.isoformat(),
                "source": "KMA-ultra-short-observation",
            }
            self._cache_put(cache_key, result)
            return self._localize(result, language)
        except self._handled_errors() as exc:
            return self._localize(
                self._error(lat, lng, nx, ny, "KMA-ultra-short-observation", exc),
                language,
            )

    def get_forecast(
        self,
        lat: float,
        lng: float,
        target_at: datetime,
        target_label: str = "미래 방문시각",
        now: datetime | None = None,
        language: str = "ko",
    ) -> dict:
        """기상청 단기예보 중 목표시각과 가장 가까운 1시간 예보를 반환한다."""
        language = self._normalize_language(language)
        if language == "en" and target_label == "미래 방문시각":
            target_label = "Future visit time"
        current = (now or datetime.now(KST)).astimezone(KST)
        target = target_at.astimezone(KST)
        nx, ny = self.latlng_to_grid(lat, lng)
        base = self._latest_vilage_base(current)
        cache_key = (
            f"forecast:{nx}:{ny}:{base:%Y%m%d%H}:{target:%Y%m%d%H}:"
            f"{language}:{target_label}"
        )
        cached = self._cache_get(cache_key)
        if cached:
            return self._localize(dict(cached), language)

        try:
            items = self._request(
                "getVilageFcst",
                {
                    "numOfRows": 1000,
                    "base_date": base.strftime("%Y%m%d"),
                    "base_time": base.strftime("%H00"),
                    "nx": nx,
                    "ny": ny,
                },
            )
            grouped: dict[datetime, dict[str, object]] = {}
            for item in items:
                forecast_at = datetime.strptime(
                    f"{item['fcstDate']}{item['fcstTime']}", "%Y%m%d%H%M"
                ).replace(tzinfo=KST)
                grouped.setdefault(forecast_at, {})[item["category"]] = item.get("fcstValue")
            if not grouped:
                raise RuntimeError("기상청 단기예보 결과가 비어 있습니다.")

            first_forecast_at = min(grouped)
            last_forecast_at = max(grouped)
            tolerance = timedelta(minutes=30)
            if target < first_forecast_at - tolerance or target > last_forecast_at + tolerance:
                if language == "en":
                    raise RuntimeError(
                        "The requested time is outside the available short-term forecast range "
                        f"({first_forecast_at.isoformat()} to {last_forecast_at.isoformat()})."
                    )
                raise RuntimeError(
                    "요청 시각이 제공된 단기예보 범위를 벗어났습니다 "
                    f"({first_forecast_at.isoformat()}~{last_forecast_at.isoformat()})."
                )

            forecast_at = min(grouped, key=lambda value: abs(value - target))
            values = grouped[forecast_at]
            temperature = self._required_float(values, "TMP")
            rainfall = self._parse_rainfall(values.get("PCP"))
            pty = int(float(values.get("PTY", 0)))
            result = {
                "available": True,
                "is_forecast": True,
                "target_label": target_label,
                "requested_for": target.isoformat(),
                "forecast_for": forecast_at.isoformat(),
                "forecast_offset_minutes": int((forecast_at - target).total_seconds() / 60),
                "location": {"lat": lat, "lng": lng, "nx": nx, "ny": ny},
                "temperature_c": temperature,
                "humidity_pct": self._float_or_none(values.get("REH")),
                "precipitation_probability_pct": self._float_or_none(values.get("POP")),
                "rainfall_mm": rainfall,
                "wind_speed_mps": self._float_or_none(values.get("WSD")),
                "condition": self._condition(pty, rainfall),
                "sky": self._sky_label(values.get("SKY")),
                "feels_like": self._feels_like(temperature),
                "base_at": base.isoformat(),
                "source": "KMA-vilage-forecast",
            }
            self._cache_put(cache_key, result)
            return self._localize(result, language)
        except self._handled_errors() as exc:
            result = self._error(lat, lng, nx, ny, "KMA-vilage-forecast", exc)
            result.update(
                {
                    "is_forecast": True,
                    "target_label": target_label,
                    "forecast_for": target.isoformat(),
                }
            )
            return self._localize(result, language)

    @staticmethod
    def _normalize_language(language: str) -> str:
        normalized = str(language or "ko").lower().replace("_", "-")
        if normalized.startswith("en"):
            return "en"
        if normalized.startswith("ko"):
            return "ko"
        raise ValueError("language must be 'ko' or 'en'.")

    @staticmethod
    def _localize(result: dict, language: str) -> dict:
        localized = dict(result)
        localized["language"] = language
        if not localized.get("available"):
            localized["summary"] = (
                "Weather information is unavailable."
                if language == "en"
                else "날씨 정보를 불러올 수 없습니다."
            )
            return localized

        condition = localized.get("condition")
        sky = localized.get("sky")
        feels_like = localized.get("feels_like")
        labels = {
            "ko": {
                "condition": {"clear": "강수 없음", "rain": "비", "snow": "눈 또는 진눈깨비"},
                "sky": {"clear": "맑음", "mostly_cloudy": "구름 많음", "cloudy": "흐림"},
                "feels_like": {"hot": "더움", "mild": "온화함", "cold": "추움"},
            },
            "en": {
                "condition": {"clear": "No precipitation", "rain": "Rain", "snow": "Snow or sleet"},
                "sky": {"clear": "Clear", "mostly_cloudy": "Mostly cloudy", "cloudy": "Cloudy"},
                "feels_like": {"hot": "Hot", "mild": "Mild", "cold": "Cold"},
            },
        }[language]
        localized["condition_label"] = labels["condition"].get(condition, condition)
        localized["sky_label"] = labels["sky"].get(sky) if sky else None
        localized["feels_like_label"] = labels["feels_like"].get(feels_like, feels_like)

        target_label = localized.get("target_label") or ("Now" if language == "en" else "현재")
        temperature = localized.get("temperature_c")
        condition_label = localized["condition_label"]
        if language == "en":
            localized["summary"] = f"{target_label}: {condition_label}, {temperature:g}°C."
        else:
            localized["summary"] = f"{target_label}: {condition_label}, {temperature:g}°C입니다."
        return localized

    def _request(self, operation: str, params: dict) -> list[dict]:
        if not self.api_key:
            raise RuntimeError("KMA_API_KEY가 설정되지 않았습니다.")
        url = f"{KMA_BASE_URL}/{operation}?" + urlencode(
            {
                "serviceKey": self.api_key,
                "pageNo": 1,
                "dataType": "JSON",
                **params,
            }
        )
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(url, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8")).get("response", {})
                break
            except (HTTPError, URLError, TimeoutError, ConnectionError, OSError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise
                time.sleep(0.25 * (attempt + 1))
        else:  # pragma: no cover - 반복문 구조상 실행되지 않는 안전장치
            raise RuntimeError(f"기상청 API 호출 실패: {last_error}")
        header = payload.get("header", {})
        if header.get("resultCode") != "00":
            raise RuntimeError(f"KMA {header.get('resultCode')}: {header.get('resultMsg')}")
        return payload.get("body", {}).get("items", {}).get("item", [])

    @staticmethod
    def _latest_vilage_base(now: datetime) -> datetime:
        candidates = []
        current = now.astimezone(KST)
        for day_offset in (0, -1):
            day = current + timedelta(days=day_offset)
            for hour in VILAGE_BASE_HOURS:
                base = day.replace(hour=hour, minute=0, second=0, microsecond=0)
                if base + timedelta(minutes=10) <= current:
                    candidates.append(base)
        if not candidates:
            raise RuntimeError("사용 가능한 기상청 단기예보 발표시각이 없습니다.")
        return max(candidates)

    @staticmethod
    def _parse_rainfall(value: object) -> float:
        text = str(value or "0").strip()
        if text in {"강수없음", "없음", "-"}:
            return 0.0
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return max(float(match.group()) if match else 0.0, 0.0)

    @staticmethod
    def _condition(pty: int, rainfall: float) -> str:
        if pty in {2, 3, 6, 7}:
            return "snow"
        if pty in {1, 4, 5} or rainfall > 0:
            return "rain"
        return "clear"

    @staticmethod
    def _sky_label(value: object) -> str | None:
        try:
            return {1: "clear", 3: "mostly_cloudy", 4: "cloudy"}.get(int(float(str(value))))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _feels_like(temperature: float) -> str:
        if temperature >= 28:
            return "hot"
        if temperature <= 8:
            return "cold"
        return "mild"

    @staticmethod
    def _float_or_none(value: object) -> float | None:
        return float(value) if value is not None else None

    @staticmethod
    def _required_float(values: dict, category: str) -> float:
        value = values.get(category)
        if value is None or str(value).strip() == "":
            raise RuntimeError(f"Required KMA field is missing: {category}")
        return float(value)

    @staticmethod
    def _handled_errors() -> tuple[type[BaseException], ...]:
        return (
            HTTPError,
            URLError,
            TimeoutError,
            ConnectionError,
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            RuntimeError,
        )

    @staticmethod
    def _error(lat: float, lng: float, nx: int, ny: int, source: str, exc: Exception) -> dict:
        return {
            "available": False,
            "location": {"lat": lat, "lng": lng, "nx": nx, "ny": ny},
            "source": source,
            "error": str(exc),
        }

    def _cache_get(self, key: str) -> dict | None:
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            self._cache.pop(key, None)
        return None

    def _cache_put(self, key: str, value: dict) -> None:
        with self._cache_lock:
            self._cache[key] = (time.monotonic() + self.cache_ttl_seconds, value)


__all__ = ["KmaWeatherClient", "KST"]
