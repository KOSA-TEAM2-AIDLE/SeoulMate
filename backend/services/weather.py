"""기상청 단기예보 API를 SeoulMate용 날씨 문맥으로 정규화한다."""

from __future__ import annotations

import math
import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from core.config import KMA_API_KEY, WEATHER_CACHE_TTL_SECONDS


KST = timezone(timedelta(hours=9))
KMA_BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
VILAGE_BASE_HOURS = (2, 5, 8, 11, 14, 17, 20, 23)
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()


def latlng_to_grid(lat: float, lng: float) -> tuple[int, int]:
    """기상청 Lambert Conformal Conic 격자 변환."""
    re = 6371.00877 / 5.0
    grid = 5.0
    slat1, slat2 = math.radians(30.0), math.radians(60.0)
    olon, olat = math.radians(126.0), math.radians(38.0)
    xo, yo = 43.0, 136.0

    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
        math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    )
    sf = (math.tan(math.pi * 0.25 + slat1 * 0.5) ** sn * math.cos(slat1)) / sn
    ro = re * sf / (math.tan(math.pi * 0.25 + olat * 0.5) ** sn)
    ra = re * sf / (math.tan(math.pi * 0.25 + math.radians(lat) * 0.5) ** sn)
    theta = math.radians(lng) - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn
    nx = int(ra * math.sin(theta) + xo + 0.5)
    ny = int(ro - ra * math.cos(theta) + yo + 0.5)
    return nx, ny


def _base_datetime(now: datetime) -> datetime:
    # 초단기실황은 매시 40분 이후 제공되므로 45분 여유를 둔다.
    return (now.astimezone(KST) - timedelta(minutes=45)).replace(minute=0, second=0, microsecond=0)


def resolve_weather_target(query: str, now: datetime | None = None) -> dict:
    """질의에서 방문 시점을 추출한다. 시각 없는 '내일'은 식당 방문 기본값 19시다."""
    current = (now or datetime.now(KST)).astimezone(KST)
    text = str(query or "").lower()

    if "모레" in text:
        day_offset, day_label = 2, "모레"
    elif "내일" in text or "tomorrow" in text:
        day_offset, day_label = 1, "내일"
    elif any(word in text for word in ("오늘", "tonight", "today")):
        day_offset, day_label = 0, "오늘"
    else:
        return {"target_at": None, "label": "현재", "is_future": False, "explicit": False}

    explicit_hour = re.search(r"(?:(오전|오후)\s*)?(\d{1,2})\s*시", text)
    english_hour = re.search(r"\b(\d{1,2})\s*(am|pm)\b", text)
    if explicit_hour:
        period, hour_text = explicit_hour.groups()
        hour = int(hour_text) % 24
        if period == "오후" and hour < 12:
            hour += 12
        elif period == "오전" and hour == 12:
            hour = 0
        elif period is None and any(word in text for word in ("저녁", "밤")) and hour < 12:
            hour += 12
        time_label = f"{hour:02d}시"
    elif english_hour:
        hour_text, period = english_hour.groups()
        hour = int(hour_text) % 12 + (12 if period == "pm" else 0)
        time_label = f"{hour:02d}시"
    elif any(word in text for word in ("아침", "morning", "breakfast")):
        hour, time_label = 9, "아침"
    elif any(word in text for word in ("점심", "noon", "lunch")):
        hour, time_label = 12, "점심"
    elif any(word in text for word in ("밤", "night")) and "tonight" not in text:
        hour, time_label = 21, "밤"
    else:
        hour = 19
        time_label = "저녁" if any(word in text for word in ("저녁", "evening", "dinner", "tonight")) else "저녁(기본 19시)"

    target = (current + timedelta(days=day_offset)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    # 이미 지난 '오늘' 시각은 과거 예보 대신 현재 실황을 사용한다.
    if day_offset == 0 and target <= current:
        return {
            "target_at": current,
            "label": f"{day_label} {time_label}(현재 시각 기준)",
            "is_future": False,
            "explicit": True,
        }
    return {
        "target_at": target,
        "label": f"{day_label} {time_label}",
        "is_future": target > current + timedelta(minutes=30),
        "explicit": True,
    }


def _vilage_base_datetime(now: datetime) -> datetime:
    current = now.astimezone(KST)
    candidates = []
    for day_offset in (0, -1):
        day = current + timedelta(days=day_offset)
        for hour in VILAGE_BASE_HOURS:
            base = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            if base + timedelta(minutes=10) <= current:
                candidates.append(base)
    if not candidates:
        raise RuntimeError("사용 가능한 기상청 단기예보 발표시각이 없습니다.")
    return max(candidates)


def _parse_rainfall(value: object) -> float:
    text = str(value or "0").strip()
    if text in {"강수없음", "없음", "-"}:
        return 0.0
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    try:
        return max(float(match.group()) if match else 0.0, 0.0)
    except (AttributeError, ValueError):
        return 0.0


def _condition(pty: int, rainfall: float) -> str:
    if pty in {2, 3, 6, 7}:
        return "snow"
    if pty in {1, 4, 5} or rainfall > 0:
        return "rain"
    return "clear"


def _feels_like(temperature: float) -> str:
    if temperature >= 28:
        return "hot"
    if temperature <= 8:
        return "cold"
    return "mild"


def _cache_get(key: str) -> dict | None:
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        _CACHE.pop(key, None)
    return None


def _cache_put(key: str, value: dict) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic() + WEATHER_CACHE_TTL_SECONDS, value)


def _request_observation(nx: int, ny: int, base: datetime) -> list[dict]:
    if not KMA_API_KEY:
        raise RuntimeError("KMA_API_KEY가 설정되지 않았습니다.")
    url = f"{KMA_BASE_URL}/getUltraSrtNcst?" + urlencode(
        {
            "serviceKey": KMA_API_KEY,
            "pageNo": 1,
            "numOfRows": 100,
            "dataType": "JSON",
            "base_date": base.strftime("%Y%m%d"),
            "base_time": base.strftime("%H00"),
            "nx": nx,
            "ny": ny,
        }
    )
    with urlopen(url, timeout=10.0) as response:
        payload = json.loads(response.read().decode("utf-8")).get("response", {})
    header = payload.get("header", {})
    if header.get("resultCode") != "00":
        raise RuntimeError(f"KMA {header.get('resultCode')}: {header.get('resultMsg')}")
    return payload.get("body", {}).get("items", {}).get("item", [])


def _request_vilage_forecast(nx: int, ny: int, base: datetime) -> list[dict]:
    if not KMA_API_KEY:
        raise RuntimeError("KMA_API_KEY가 설정되지 않았습니다.")
    url = f"{KMA_BASE_URL}/getVilageFcst?" + urlencode(
        {
            "serviceKey": KMA_API_KEY,
            "pageNo": 1,
            "numOfRows": 1000,
            "dataType": "JSON",
            "base_date": base.strftime("%Y%m%d"),
            "base_time": base.strftime("%H00"),
            "nx": nx,
            "ny": ny,
        }
    )
    with urlopen(url, timeout=10.0) as response:
        payload = json.loads(response.read().decode("utf-8")).get("response", {})
    header = payload.get("header", {})
    if header.get("resultCode") != "00":
        raise RuntimeError(f"KMA {header.get('resultCode')}: {header.get('resultMsg')}")
    return payload.get("body", {}).get("items", {}).get("item", [])


def _sky_label(value: object) -> str | None:
    try:
        return {1: "clear", 3: "mostly_cloudy", 4: "cloudy"}.get(int(float(str(value))))
    except (TypeError, ValueError):
        return None


def get_forecast_context(
    lat: float,
    lng: float,
    target_at: datetime,
    target_label: str,
    now: datetime | None = None,
) -> dict:
    """단기예보에서 방문 목표시각과 가장 가까운 1시간 예보를 정규화한다."""
    current = (now or datetime.now(KST)).astimezone(KST)
    target = target_at.astimezone(KST)
    nx, ny = latlng_to_grid(lat, lng)
    base = _vilage_base_datetime(current)
    cache_key = f"forecast:{nx}:{ny}:{base:%Y%m%d%H}:{target:%Y%m%d%H}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        items = _request_vilage_forecast(nx, ny, base)
        grouped: dict[datetime, dict[str, object]] = {}
        for item in items:
            forecast_at = datetime.strptime(
                f"{item['fcstDate']}{item['fcstTime']}", "%Y%m%d%H%M"
            ).replace(tzinfo=KST)
            grouped.setdefault(forecast_at, {})[item["category"]] = item.get("fcstValue")
        if not grouped:
            raise RuntimeError("기상청 단기예보 결과가 비어 있습니다.")
        forecast_at = min(grouped, key=lambda value: abs(value - target))
        values = grouped[forecast_at]
        temperature = float(values.get("TMP", 0))
        rainfall = _parse_rainfall(values.get("PCP"))
        pty = int(float(values.get("PTY", 0)))
        context = {
            "available": True,
            "is_forecast": True,
            "target_label": target_label,
            "forecast_for": forecast_at.isoformat(),
            "location": {"lat": lat, "lng": lng, "nx": nx, "ny": ny},
            "temperature_c": temperature,
            "humidity_pct": float(values["REH"]) if values.get("REH") is not None else None,
            "precipitation_probability_pct": float(values["POP"]) if values.get("POP") is not None else None,
            "rainfall_mm": rainfall,
            "wind_speed_mps": float(values["WSD"]) if values.get("WSD") is not None else None,
            "condition": _condition(pty, rainfall),
            "sky": _sky_label(values.get("SKY")),
            "feels_like": _feels_like(temperature),
            "base_at": base.isoformat(),
            "source": "KMA-vilage-forecast",
        }
        _cache_put(cache_key, context)
        return context
    except (
        HTTPError, URLError, TimeoutError, json.JSONDecodeError,
        KeyError, TypeError, ValueError, RuntimeError,
    ) as exc:
        return {
            "available": False,
            "is_forecast": True,
            "target_label": target_label,
            "forecast_for": target.isoformat(),
            "location": {"lat": lat, "lng": lng, "nx": nx, "ny": ny},
            "source": "KMA-vilage-forecast",
            "error": str(exc),
        }


def get_weather_for_query(
    query: str,
    lat: float,
    lng: float,
    now: datetime | None = None,
) -> dict:
    current = (now or datetime.now(KST)).astimezone(KST)
    target = resolve_weather_target(query, current)
    if target["is_future"]:
        return get_forecast_context(
            lat, lng, target["target_at"], target["label"], now=current
        )
    context = dict(get_weather_context(lat, lng, now=current))
    context["is_forecast"] = False
    context["target_label"] = target["label"]
    context["forecast_for"] = current.isoformat()
    return context


def get_weather_context(lat: float, lng: float, now: datetime | None = None) -> dict:
    nx, ny = latlng_to_grid(lat, lng)
    base = _base_datetime(now or datetime.now(KST))
    cache_key = f"{nx}:{ny}:{base:%Y%m%d%H}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        items = _request_observation(nx, ny, base)
        if not items:
            base -= timedelta(hours=1)
            items = _request_observation(nx, ny, base)
        values = {item["category"]: item.get("obsrValue") for item in items}
        temperature = float(values.get("T1H", 0))
        rainfall = _parse_rainfall(values.get("RN1"))
        pty = int(float(values.get("PTY", 0)))
        context = {
            "available": True,
            "location": {"lat": lat, "lng": lng, "nx": nx, "ny": ny},
            "temperature_c": temperature,
            "humidity_pct": float(values["REH"]) if values.get("REH") is not None else None,
            "rainfall_mm": rainfall,
            "wind_speed_mps": float(values["WSD"]) if values.get("WSD") is not None else None,
            "condition": _condition(pty, rainfall),
            "feels_like": _feels_like(temperature),
            "observed_at": base.isoformat(),
            "source": "KMA",
        }
        _cache_put(cache_key, context)
        return context
    except (
        HTTPError, URLError, TimeoutError, json.JSONDecodeError,
        KeyError, TypeError, ValueError, RuntimeError,
    ) as exc:
        return {
            "available": False,
            "location": {"lat": lat, "lng": lng, "nx": nx, "ny": ny},
            "source": "KMA",
            "error": str(exc),
        }
