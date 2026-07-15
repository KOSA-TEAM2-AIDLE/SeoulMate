import asyncio
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from core.config import DATA_DIR, Settings, settings
from schemas.congestion import (
    CongestionForecast,
    CongestionLevel,
    CongestionSnapshot,
    LocationCongestionResult,
    NearbyCongestionResult,
    PopulationDemographics,
    SeoulApiForecast,
    SeoulApiPopulation,
    SeoulApiPopulationResponse,
)
from services.poi_matcher import PoiMatcher


class CongestionServiceError(Exception):
    """혼잡도 서비스에서 발생하는 모든 예외의 부모 클래스."""


class SeoulApiKeyMissingError(CongestionServiceError):
    """서울 열린데이터광장 API 키가 없을 때 발생."""


class SeoulApiRequestError(CongestionServiceError):
    """서울 API 연결, timeout, HTTP 요청 실패 시 발생."""


class SeoulApiResponseError(CongestionServiceError):
    """서울 API 응답 형식 또는 결과 코드가 올바르지 않을 때 발생."""


class SeoulApiDataNotFoundError(CongestionServiceError):
    """정상 응답에 조회 장소 데이터가 없을 때 발생."""


class SeoulPopulationClient:
    SERVICE_NAME = "citydata_ppltn"
    RESPONSE_TYPE = "json"
    START_INDEX = 1
    END_INDEX = 5
    SUCCESS_CODE = "INFO-000"

    def __init__(self, config: Settings | None = None) -> None:
        self._config = config or settings

    # API 키 조회
    def _get_api_key(self) -> str:
        secret = self._config.seoul_open_api_key

        if secret is None:
            raise SeoulApiKeyMissingError(
                "서울 열린데이터광장 API 키가 설정되지 않았습니다."
            )

        api_key = secret.get_secret_value().strip()

        if not api_key:
            raise SeoulApiKeyMissingError(
                "서울 열린데이터광장 API 키가 비어 있습니다."
            )

        return api_key

    # 입력 장소에 대한 전처리 함수
    def _build_url(self, area: str) -> str:
        normalized_area = area.strip()

        if not normalized_area:
            raise ValueError("조회할 장소명 또는 장소코드가 필요합니다.")

        encoded_area = quote(normalized_area, safe="")
        base_url = self._config.seoul_api_base_url.rstrip("/")
        api_key = self._get_api_key()

        return (
            f"{base_url}/{api_key}/{self.RESPONSE_TYPE}/"
            f"{self.SERVICE_NAME}/{self.START_INDEX}/"
            f"{self.END_INDEX}/{encoded_area}"
        )

    async def fetch_population(
        self,
        area: str,
    ) -> SeoulApiPopulationResponse:
        url = self._build_url(area)

        try:
            async with httpx.AsyncClient(
                timeout=self._config.seoul_api_timeout_seconds
            ) as client:
                response = await client.get(
                    url,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()

        except httpx.TimeoutException:
            raise SeoulApiRequestError(
                "서울시 실시간 인구 API 요청 시간이 초과되었습니다."
            ) from None
        except httpx.HTTPStatusError:
            raise SeoulApiRequestError(
                "서울시 실시간 인구 API가 HTTP 오류를 반환했습니다."
            ) from None
        except httpx.RequestError:
            raise SeoulApiRequestError(
                "서울시 실시간 인구 API에 연결할 수 없습니다."
            ) from None

        try:
            payload = response.json()
        except ValueError:
            raise SeoulApiResponseError(
                "서울시 API 응답을 JSON으로 해석할 수 없습니다."
            ) from None

        try:
            validated = SeoulApiPopulationResponse.model_validate(payload)
        except ValidationError:
            raise SeoulApiResponseError(
                "서울시 API 응답 구조가 예상한 형식과 다릅니다."
            ) from None

        if validated.result.code != self.SUCCESS_CODE:
            raise SeoulApiResponseError(
                f"서울시 API 요청 실패: {validated.result.message}"
            )

        if not validated.populations:
            raise SeoulApiDataNotFoundError(
                "조회한 장소의 실시간 인구 데이터가 없습니다."
            )

        return validated


# API 응답의 결과 Parsing 을 위한 변수 선언
SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")
SEOUL_DATETIME_FORMAT = "%Y-%m-%d %H:%M"

# MCP 내부적으로 점수 변환 기준 선언
CONGESTION_SCORES = {
    CongestionLevel.RELAXED: 25,
    CongestionLevel.NORMAL: 50,
    CongestionLevel.CROWDED: 75,
    CongestionLevel.VERY_CROWDED: 100,
}

def _parse_seoul_datetime(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, SEOUL_DATETIME_FORMAT)
    except ValueError:
        raise SeoulApiResponseError(
            f"서울시 API의 날짜 형식이 올바르지 않습니다: {value}"
        ) from None

    return parsed.replace(tzinfo=SEOUL_TIMEZONE)

def _validate_population_range(
    population_min: int,
    population_max: int,
) -> None:
    if population_min > population_max:
        raise SeoulApiResponseError(
            "서울시 API의 최소 인구가 최대 인구보다 큽니다."
        )
    
def _build_demographics(
    population: SeoulApiPopulation,
) -> PopulationDemographics:
    return PopulationDemographics(
        male_rate=population.male_rate,
        female_rate=population.female_rate,
        age_0_to_10_rate=population.age_0_to_10_rate,
        age_10_rate=population.age_10_rate,
        age_20_rate=population.age_20_rate,
        age_30_rate=population.age_30_rate,
        age_40_rate=population.age_40_rate,
        age_50_rate=population.age_50_rate,
        age_60_rate=population.age_60_rate,
        age_70_plus_rate=population.age_70_plus_rate,
        resident_rate=population.resident_rate,
        non_resident_rate=population.non_resident_rate,
    )

def _build_forecast(
    forecast: SeoulApiForecast,
) -> CongestionForecast:
    _validate_population_range(
        forecast.population_min,
        forecast.population_max,
    )

    return CongestionForecast(
        forecast_at=_parse_seoul_datetime(forecast.forecast_time),
        congestion_level=forecast.congestion_level,
        population_min=forecast.population_min,
        population_max=forecast.population_max,
    )

def _build_snapshot(
    response: SeoulApiPopulationResponse,
) -> CongestionSnapshot:
    if len(response.populations) != 1:
        raise SeoulApiResponseError(
            "서울시 API의 장소 응답 개수가 올바르지 않습니다."
        )

    population = response.populations[0]

    _validate_population_range(
        population.population_min,
        population.population_max,
    )

    forecasts = [
        _build_forecast(forecast)
        for forecast in (population.forecasts or [])
    ]

    return CongestionSnapshot(
        area_name=population.area_name,
        area_code=population.area_code,
        congestion_level=population.congestion_level,
        congestion_score=CONGESTION_SCORES[
            population.congestion_level
        ],
        congestion_message=population.congestion_message,
        population_min=population.population_min,
        population_max=population.population_max,
        observed_at=_parse_seoul_datetime(
            population.population_time
        ),
        fetched_at=datetime.now(SEOUL_TIMEZONE),
        is_replacement_data=population.replacement_yn == "Y",
        forecast_available=population.forecast_yn == "Y",
        demographics=_build_demographics(population),
        forecasts=forecasts,
    )

class CongestionService:
    def __init__(
        self,
        client: SeoulPopulationClient | None = None,
        poi_matcher: PoiMatcher | None = None,
    ) -> None:
        self._client = client or SeoulPopulationClient() # 테스트를 위해 client 를 생성자로 주입받을 수 있도록 구현 
        self._poi_matcher = poi_matcher

    async def get_congestion(
        self,
        area: str,
    ) -> CongestionSnapshot:
        response = await self._client.fetch_population(area)
        return _build_snapshot(response)

    async def get_congestion_by_location(
        self,
        latitude: float,
        longitude: float,
    ) -> LocationCongestionResult:
        poi_match = self._get_poi_matcher().match(latitude, longitude)
        congestion = await self.get_congestion(poi_match.area_code)

        if congestion.area_code != poi_match.area_code:
            raise SeoulApiResponseError(
                "매핑한 POI 코드와 서울시 API 응답 코드가 일치하지 않습니다."
            )

        return LocationCongestionResult(
            poi_match=poi_match,
            congestion=congestion,
        )

    async def get_nearby_congestion(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float = 3_000,
        limit: int = 5,
    ) -> NearbyCongestionResult:
        poi_matches = self._get_poi_matcher().find_nearby(
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            limit=limit,
        )
        snapshots = await asyncio.gather(
            *(
                self.get_congestion(poi_match.area_code)
                for poi_match in poi_matches
            )
        )

        areas: list[LocationCongestionResult] = []
        for poi_match, snapshot in zip(poi_matches, snapshots, strict=True):
            if snapshot.area_code != poi_match.area_code:
                raise SeoulApiResponseError(
                    "매핑한 POI 코드와 서울시 API 응답 코드가 "
                    "일치하지 않습니다."
                )
            areas.append(
                LocationCongestionResult(
                    poi_match=poi_match,
                    congestion=snapshot,
                )
            )

        return NearbyCongestionResult(
            center_latitude=latitude,
            center_longitude=longitude,
            radius_meters=radius_meters,
            areas=areas,
        )

    def _get_poi_matcher(self) -> PoiMatcher:
        if self._poi_matcher is None:
            path = (
                DATA_DIR
                / "seoul_poi"
                / "processed"
                / "seoul_poi_areas.geojson"
            )
            self._poi_matcher = PoiMatcher.from_file(path)
        return self._poi_matcher
