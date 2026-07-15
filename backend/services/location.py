"""사용자 질의의 서울 지명 추출, 카카오 지오코딩, 거리 계산."""

from __future__ import annotations

import math
import json
import re
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.config import KAKAO_REST_API_KEY


LOCATION_SUFFIXES = (
    "동", "구", "역", "궁", "타워", "대교", "공원", "시장", "대학교",
    "병원", "터미널", "공항", "거리", "광장",
)
SEOUL_CENTER = (37.5665, 126.9780)
_GEOCODE_SUCCESS_CACHE: dict[str, tuple[float, float, str]] = {}

# 카카오 키워드 검색에서 권역명이 관광지·행정명과 충돌하는 경우가 있어
# 식당 검색 반경의 기준으로 쓰기 좋은 대표 역을 명시한다.
SEOUL_AREA_SEARCH_ALIASES = {
    "강남": "강남역",
    "홍대": "홍대입구역",
    "성수": "성수역",
    "이태원": "이태원역",
    "잠실": "잠실역",
    "여의도": "여의도역",
    "명동": "명동역",
    "신촌": "신촌역",
    "광화문": "광화문역",
    "hongdae": "Hongdae station",
    "gangnam": "Gangnam station",
}


def location_candidates(query: str) -> list[str]:
    words = query.split()
    candidates: list[str] = []
    for size in (3, 2, 1):
        for index in range(len(words) - size + 1):
            last_word = words[index + size - 1]
            if last_word.endswith(LOCATION_SUFFIXES) and len(last_word) >= 2:
                candidates.append(" ".join(words[index:index + size]))
    return list(dict.fromkeys(candidates))


def geocode_kakao(place_text: str) -> Optional[tuple[float, float, str]]:
    if not KAKAO_REST_API_KEY:
        return None
    cache_key = place_text.strip().lower()
    if cache_key in _GEOCODE_SUCCESS_CACHE:
        return _GEOCODE_SUCCESS_CACHE[cache_key]
    try:
        search_text = SEOUL_AREA_SEARCH_ALIASES.get(place_text.strip().lower(), place_text)
        url = "https://dapi.kakao.com/v2/local/search/keyword.json?" + urlencode(
            {"query": search_text, "size": 1}
        )
        request = Request(url, headers={"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"})
        with urlopen(request, timeout=3.0) as response:
            documents = json.loads(response.read().decode("utf-8")).get("documents", [])
        if not documents:
            return None
        top = documents[0]
        lat, lng = float(top["y"]), float(top["x"])
        if not (37.4 <= lat <= 37.7 and 126.7 <= lng <= 127.3):
            return None
        result = (lat, lng, top.get("place_name") or place_text)
        # 실패는 캐시하지 않아 일시적인 네트워크 오류가 프로세스 수명 동안 고착되지 않게 한다.
        _GEOCODE_SUCCESS_CACHE[cache_key] = result
        return result
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def extract_location(query: str) -> tuple[Optional[str], Optional[float], Optional[float], str]:
    for candidate in location_candidates(query):
        geocoded = geocode_kakao(candidate)
        if not geocoded:
            continue
        lat, lng, name = geocoded
        cleaned = re.sub(r"\s+", " ", query.replace(candidate, "", 1)).strip()
        return name, lat, lng, cleaned
    return None, None, None, query


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
