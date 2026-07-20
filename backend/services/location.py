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
CITYWIDE_LOCATION_NAME = "서울 전체"
_GEOCODE_SUCCESS_CACHE: dict[str, tuple[float, float, str]] = {}

# 위치 재질문에 대한 답변과 처음부터 입력한 광역 검색 표현을 하나의 값으로
# 정규화한다. 공백과 문장부호를 제거한 뒤 비교하므로 "아무 데나"와
# "아무데나"를 같은 표현으로 처리한다.
_CITYWIDE_LOCATION_PHRASES = frozenset({
    "서울", "서울전체", "서울전역", "서울전지역", "서울권전체", "서울시내전체",
    "서울어디든", "서울어디든지", "서울어디나", "서울어디라도", "서울아무데나",
    "서울아무곳이나", "서울아무지역이나", "서울내어디든", "서울안이면어디든",
    "서울이면어디든", "서울이라면어디든",
    "아무데나", "아무데든", "아무곳이나", "아무곳이든", "아무지역이나",
    "아무지역이든", "아무동네나", "아무동네든", "아무장소나", "아무장소든",
    "어디든", "어디든지", "어디나", "어디라도", "어디여도", "어디라도괜찮아",
    "어디든괜찮아", "어디든좋아", "어느곳이든", "어느지역이든", "어느동네든",
    "지역상관없어", "지역상관없어요", "지역상관없습니다", "지역상관없음",
    "위치상관없어", "위치상관없어요", "위치상관없습니다", "위치상관없음",
    "장소상관없어", "장소상관없어요", "장소상관없습니다", "장소상관없음",
    "동네상관없어", "동네상관없어요", "동네상관없습니다", "동네상관없음",
    "지역무관", "지역무관해", "위치무관", "장소무관", "동네무관",
    "지역제한없어", "지역제한없음", "지역조건없어", "지역조건없음",
    "상관없어", "상관없어요", "상관없습니다", "상관없음", "무관",
    "anywhere", "anywhereinseoul", "anyarea", "anylocation", "anyplace",
    "wherever", "nopreference", "nolocationspecific", "locationdoesntmatter",
    "locationdoesnotmatter", "allofseoul", "seoulwide", "acrossseoul",
})

_CITYWIDE_EXPLICIT_MARKERS = (
    "서울전체", "서울전역", "서울전지역", "서울권전체", "서울시내전체",
    "서울어디든", "서울어디나", "서울어디라도", "서울아무데나", "서울아무곳이나",
    "서울내어디든", "서울안이면어디든", "서울이면어디든", "서울이라면어디든",
    "아무데나", "아무데든", "아무곳이나", "아무곳이든", "아무지역이나",
    "아무지역이든", "아무동네나", "아무동네든", "어디든", "어디든지",
    "어디라도", "어디여도", "어느곳이든", "어느지역이든", "어느동네든",
    "anywhere", "anyarea", "anylocation", "anyplace", "wherever", "allofseoul",
    "seoulwide", "acrossseoul",
)

_CITYWIDE_GENERIC_MARKERS = (
    "지역상관없", "위치상관없", "장소상관없", "동네상관없",
    "지역무관", "위치무관", "장소무관", "동네무관",
    "지역제한없", "지역조건없", "상관없", "nopreference",
    "locationdoesntmatter", "locationdoesnotmatter",
)

# 권역명은 카카오 키워드 검색 결과가 관광지나 동명의 시설로 흔들릴 수 있다.
# 식당 반경 검색에 필요한 것은 정밀 주소가 아니라 안정적인 권역 중심점이므로,
# 자주 쓰는 서울 권역은 외부 API보다 이 대표 좌표를 우선한다.
SEOUL_AREA_COORDINATES: dict[str, tuple[float, float, str]] = {
    "서울": (*SEOUL_CENTER, "서울"),
    "강남": (37.4979, 127.0276, "강남역"),
    "강남역": (37.4979, 127.0276, "강남역"),
    "홍대": (37.5572, 126.9254, "홍대입구역"),
    "홍대입구": (37.5572, 126.9254, "홍대입구역"),
    "홍대입구역": (37.5572, 126.9254, "홍대입구역"),
    "성수": (37.5446, 127.0559, "성수역"),
    "성수동": (37.5446, 127.0559, "성수역"),
    "성수역": (37.5446, 127.0559, "성수역"),
    "이태원": (37.5345, 126.9946, "이태원역"),
    "이태원역": (37.5345, 126.9946, "이태원역"),
    "잠실": (37.5133, 127.1002, "잠실역"),
    "잠실역": (37.5133, 127.1002, "잠실역"),
    "여의도": (37.5216, 126.9243, "여의도역"),
    "여의도역": (37.5216, 126.9243, "여의도역"),
    "명동": (37.5609, 126.9863, "명동역"),
    "명동역": (37.5609, 126.9863, "명동역"),
    "신촌": (37.5551, 126.9369, "신촌역"),
    "신촌역": (37.5551, 126.9369, "신촌역"),
    "광화문": (37.5716, 126.9769, "광화문역"),
    "광화문역": (37.5716, 126.9769, "광화문역"),
    "대학로": (37.5822, 127.0019, "혜화역"),
    "혜화": (37.5822, 127.0019, "혜화역"),
    "혜화역": (37.5822, 127.0019, "혜화역"),
    "종로": (37.5702, 126.9831, "종각역"),
    "종각": (37.5702, 126.9831, "종각역"),
    "종각역": (37.5702, 126.9831, "종각역"),
    "을지로": (37.5660, 126.9820, "을지로입구역"),
    "을지로입구": (37.5660, 126.9820, "을지로입구역"),
    "연남": (37.5627, 126.9220, "연남동"),
    "연남동": (37.5627, 126.9220, "연남동"),
    "합정": (37.5495, 126.9137, "합정역"),
    "합정역": (37.5495, 126.9137, "합정역"),
    "망원": (37.5560, 126.9100, "망원역"),
    "망원역": (37.5560, 126.9100, "망원역"),
    "건대": (37.5404, 127.0692, "건대입구역"),
    "건대입구": (37.5404, 127.0692, "건대입구역"),
    "건대입구역": (37.5404, 127.0692, "건대입구역"),
    "hongdae": (37.5572, 126.9254, "Hongdae"),
    "gangnam": (37.4979, 127.0276, "Gangnam"),
    "seongsu": (37.5446, 127.0559, "Seongsu"),
    "jongno": (37.5702, 126.9831, "Jongno"),
    "daehangno": (37.5822, 127.0019, "Daehangno"),
}

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

# 대표 권역 좌표와 DB 주소가 서로 다른 잘못된 행을 검색 단계에서 거르기 위한
# 최소 안전장치다. 주소에 자치구가 명시된 경우에만 검사한다.
SEOUL_AREA_ALLOWED_DISTRICTS: dict[str, frozenset[str]] = {
    "경복궁": frozenset({"종로구"}),
    "강남": frozenset({"강남구", "서초구"}),
    "강남역": frozenset({"강남구", "서초구"}),
    "홍대": frozenset({"마포구", "서대문구"}),
    "홍대입구": frozenset({"마포구", "서대문구"}),
    "홍대입구역": frozenset({"마포구", "서대문구"}),
    "연남": frozenset({"마포구", "서대문구"}),
    "연남동": frozenset({"마포구", "서대문구"}),
    "합정": frozenset({"마포구", "영등포구"}),
    "합정역": frozenset({"마포구", "영등포구"}),
    "망원": frozenset({"마포구", "서대문구"}),
    "망원역": frozenset({"마포구", "서대문구"}),
    "신촌": frozenset({"서대문구", "마포구"}),
    "신촌역": frozenset({"서대문구", "마포구"}),
    "성수": frozenset({"성동구", "광진구"}),
    "성수동": frozenset({"성동구", "광진구"}),
    "성수역": frozenset({"성동구", "광진구"}),
    "이태원": frozenset({"용산구"}),
    "이태원역": frozenset({"용산구"}),
    "잠실": frozenset({"송파구", "광진구", "강동구"}),
    "잠실역": frozenset({"송파구", "광진구", "강동구"}),
    "여의도": frozenset({"영등포구", "마포구"}),
    "여의도역": frozenset({"영등포구", "마포구"}),
    "명동": frozenset({"중구", "종로구", "용산구"}),
    "명동역": frozenset({"중구", "종로구", "용산구"}),
    "광화문": frozenset({"종로구", "중구", "서대문구"}),
    "광화문역": frozenset({"종로구", "중구", "서대문구"}),
    "종로": frozenset({"종로구", "중구"}),
    "종각": frozenset({"종로구", "중구"}),
    "종각역": frozenset({"종로구", "중구"}),
    "을지로": frozenset({"중구", "종로구"}),
    "을지로입구": frozenset({"중구", "종로구"}),
    "대학로": frozenset({"종로구", "성북구"}),
    "혜화": frozenset({"종로구", "성북구"}),
    "혜화역": frozenset({"종로구", "성북구"}),
    "건대": frozenset({"광진구", "성동구"}),
    "건대입구": frozenset({"광진구", "성동구"}),
    "건대입구역": frozenset({"광진구", "성동구"}),
    "hongdae": frozenset({"마포구", "서대문구"}),
    "gangnam": frozenset({"강남구", "서초구"}),
    "seongsu": frozenset({"성동구", "광진구"}),
    "jongno": frozenset({"종로구", "중구"}),
    "daehangno": frozenset({"종로구", "성북구"}),
}

LOCATION_PARTICLES = (
    "에서부터", "으로부터", "근처에서", "주변에서", "에서", "으로", "로", "에",
)


def _normalized_area_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def _compact_preference_text(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.strip().lower())


# 서울 25개 자치구(한글 → 로마자). ko/en 주소·지명을 canonical 한글 구로 통일해
# 비교하기 위한 테이블. 사용자가 특정 구를 지정하면 그 구로 결과를 제한한다.
_SEOUL_DISTRICT_EN: dict[str, str] = {
    "강남구": "gangnam-gu", "강동구": "gangdong-gu", "강북구": "gangbuk-gu",
    "강서구": "gangseo-gu", "관악구": "gwanak-gu", "광진구": "gwangjin-gu",
    "구로구": "guro-gu", "금천구": "geumcheon-gu", "노원구": "nowon-gu",
    "도봉구": "dobong-gu", "동대문구": "dongdaemun-gu", "동작구": "dongjak-gu",
    "마포구": "mapo-gu", "서대문구": "seodaemun-gu", "서초구": "seocho-gu",
    "성동구": "seongdong-gu", "성북구": "seongbuk-gu", "송파구": "songpa-gu",
    "양천구": "yangcheon-gu", "영등포구": "yeongdeungpo-gu", "용산구": "yongsan-gu",
    "은평구": "eunpyeong-gu", "종로구": "jongno-gu", "중구": "jung-gu",
    "중랑구": "jungnang-gu",
}
# 지명 토큰(정규화) → canonical 한글 구. 완전형/생략형, 한글/로마자를 모두 담는다.
_DISTRICT_LOOKUP: dict[str, str] = {}
for _ko, _en in _SEOUL_DISTRICT_EN.items():
    for _tok in (_ko, _ko[:-1], _en, _en[: -len("-gu")]):
        _DISTRICT_LOOKUP.setdefault(_tok.lower(), _ko)


def _resolve_explicit_district(location_name: str) -> frozenset[str] | None:
    """지명이 특정 자치구를 가리키면 {canonical 한글 구}, 아니면 None."""
    key = _normalized_area_key(location_name)
    if key in _DISTRICT_LOOKUP:
        return frozenset({_DISTRICT_LOOKUP[key]})
    match = re.search(r"([가-힣]{1,6}구)|([a-z]+-gu)", key)
    if match:
        token = (match.group(1) or match.group(2)).lower()
        if token in _DISTRICT_LOOKUP:
            return frozenset({_DISTRICT_LOOKUP[token]})
    return None


def _address_districts(address: str) -> set[str]:
    """주소에서 자치구를 canonical 한글 구 집합으로 뽑는다(ko·en 주소 모두)."""
    found: set[str] = set()
    for match in re.finditer(r"([가-힣]{1,6}구)", address):
        found.add(match.group(1))
    for match in re.finditer(r"([A-Za-z]+-gu)", address):
        canonical = _DISTRICT_LOOKUP.get(match.group(1).lower())
        if canonical:
            found.add(canonical)
    return found


def address_matches_search_area(location_name: str | None, address: str | None) -> bool:
    """대표 권역/특정 구와 주소의 자치구가 명백히 충돌할 때만 False를 반환한다."""
    if not location_name or not address:
        return True
    allowed = SEOUL_AREA_ALLOWED_DISTRICTS.get(_normalized_area_key(location_name))
    if not allowed:
        # 콜로퀴얼 권역 맵에 없으면, 사용자가 특정 자치구(용산구/Yongsan-gu 등)를
        # 지정했는지 판정해 그 구로 제한한다. (ko/en 공통)
        allowed = _resolve_explicit_district(location_name)
    if not allowed:
        return True
    found = _address_districts(address)
    if not found:
        return True
    return bool(found & allowed)


def is_citywide_location(value: str | None) -> bool:
    """구조화된 위치값이 서울 전역/지역 무관 의미인지 판정한다."""
    if not value:
        return False
    return _compact_preference_text(value) in _CITYWIDE_LOCATION_PHRASES


def wants_citywide_search(
    text: str | None,
    *,
    location_clarification: bool = False,
) -> bool:
    """자유 문장에서 서울 전역 검색 의도를 찾는다.

    단독 ``상관없어``는 주차·가격 등에 대한 말일 수도 있으므로 위치 재질문에
    답하는 상황에서만 광역 위치로 인정한다.
    """
    if not text:
        return False
    if is_citywide_location(text):
        return True
    compact = _compact_preference_text(text)
    if any(marker in compact for marker in _CITYWIDE_EXPLICIT_MARKERS):
        return True
    if location_clarification and any(
        marker in compact for marker in _CITYWIDE_GENERIC_MARKERS
    ):
        return True
    # '서울 식당 추천'의 서울은 광역 검색이지만 '서울시청 근처'는 구체 지명이다.
    return bool(re.search(r"(?<![가-힣])서울(?![가-힣])", text))


def _looks_like_location(value: str) -> bool:
    key = _normalized_area_key(value)
    return key in SEOUL_AREA_COORDINATES or value.endswith(LOCATION_SUFFIXES)


def _strip_location_particle(value: str) -> str:
    cleaned = value.strip(".,!?;:'\"()[]{}")
    for particle in LOCATION_PARTICLES:
        if cleaned.endswith(particle):
            base = cleaned[:-len(particle)]
            if len(base) >= 2 and _looks_like_location(base):
                return base
    return cleaned


def location_candidates(query: str) -> list[str]:
    words = [_strip_location_particle(word) for word in query.split()]
    candidates: list[str] = []

    # '홍대', '대학로'처럼 행정구역 접미사가 없는 권역도 먼저 찾는다.
    # 긴 별칭부터 검사해 '홍대입구역'이 '홍대'로 잘리는 일을 막는다.
    for alias in sorted(SEOUL_AREA_COORDINATES, key=len, reverse=True):
        pattern = re.escape(alias) + r"(?:에서부터|으로부터|근처에서|주변에서|에서|으로|로|에)?(?=\s|[,.!?;:]|$)"
        if re.search(pattern, query, flags=re.IGNORECASE):
            candidates.append(alias)

    for size in (3, 2, 1):
        for index in range(len(words) - size + 1):
            last_word = words[index + size - 1]
            if last_word.endswith(LOCATION_SUFFIXES) and len(last_word) >= 2:
                candidates.append(" ".join(words[index:index + size]))
    return list(dict.fromkeys(candidates))


def _kakao_search(endpoint: str, query: str) -> list[dict]:
    url = f"https://dapi.kakao.com/v2/local/search/{endpoint}.json?" + urlencode(
        {"query": query, "size": 3}
    )
    request = Request(url, headers={"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"})
    with urlopen(request, timeout=3.0) as response:
        return json.loads(response.read().decode("utf-8")).get("documents", [])


def _seoul_documents(documents: list[dict]) -> list[dict]:
    return [
        document
        for document in documents
        if str(document.get("address_name") or "").startswith("서울")
        or str(
            (document.get("road_address") or {}).get("address_name") or ""
        ).startswith("서울")
    ]


def geocode_kakao(place_text: str) -> Optional[tuple[float, float, str]]:
    cache_key = _normalized_area_key(place_text)
    stable_area = SEOUL_AREA_COORDINATES.get(cache_key)
    if stable_area is not None:
        return stable_area
    if not KAKAO_REST_API_KEY:
        return None
    if cache_key in _GEOCODE_SUCCESS_CACHE:
        return _GEOCODE_SUCCESS_CACHE[cache_key]
    try:
        search_text = SEOUL_AREA_SEARCH_ALIASES.get(place_text.strip().lower(), place_text)
        documents = _seoul_documents(_kakao_search("keyword", search_text))
        # '연희동', '서교동' 같은 행정동은 키워드(장소) 검색에 없을 수 있다.
        # 다른 시·도의 동명 장소만 나온 경우도 주소 검색을 사용한다.
        if not documents:
            address_query = place_text if "서울" in place_text else f"서울 {place_text}"
            documents = _seoul_documents(_kakao_search("address", address_query))
        if not documents:
            return None
        top = documents[0]
        lat, lng = float(top["y"]), float(top["x"])
        if not (37.4 <= lat <= 37.7 and 126.7 <= lng <= 127.3):
            return None
        result = (
            lat,
            lng,
            top.get("place_name") or top.get("address_name") or place_text,
        )
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
        candidate_pattern = re.escape(candidate) + (
            r"(?:에서부터|으로부터|근처에서|주변에서|에서|으로|로|에)?"
        )
        cleaned = re.sub(candidate_pattern, " ", query, count=1, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return name, lat, lng, cleaned
    return None, None, None, query


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
