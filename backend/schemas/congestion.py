from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from schemas.poi import PoiMatch


class CongestionLevel(str, Enum):
    RELAXED = "여유"
    NORMAL = "보통"
    CROWDED = "약간 붐빔"
    VERY_CROWDED = "붐빔"


# 서울시 API 모델의 공통 부모
class SeoulApiModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, # Python 필드명과 API alias 양쪽 설정으로 모두 객체 생성이 가능하다.
        extra="ignore",
    )


# 응답 결과가 200이여도 원하는 결과인지, 아닌지 확인
class SeoulApiResult(SeoulApiModel):
    code: str = Field(alias="RESULT.CODE")
    message: str = Field(alias="RESULT.MESSAGE")

# 공식 실시간 API 예측값 
class SeoulApiForecast(SeoulApiModel):
    forecast_time: str = Field(alias="FCST_TIME")
    congestion_level: CongestionLevel = Field(alias="FCST_CONGEST_LVL")
    population_min: int = Field(alias="FCST_PPLTN_MIN", ge=0)
    population_max: int = Field(alias="FCST_PPLTN_MAX", ge=0)


# 공식 실시간 인구 API 
class SeoulApiPopulation(SeoulApiModel):
    area_name: str = Field(alias="AREA_NM")
    area_code: str = Field(alias="AREA_CD")

    congestion_level: CongestionLevel = Field(alias="AREA_CONGEST_LVL")
    congestion_message: str = Field(alias="AREA_CONGEST_MSG")
    population_min: int = Field(alias="AREA_PPLTN_MIN", ge=0)
    population_max: int = Field(alias="AREA_PPLTN_MAX", ge=0)

    male_rate: float | None = Field(default=None, alias="MALE_PPLTN_RATE")
    female_rate: float | None = Field(default=None, alias="FEMALE_PPLTN_RATE")

    age_0_to_10_rate: float | None = Field(default=None, alias="PPLTN_RATE_0")
    age_10_rate: float | None = Field(default=None, alias="PPLTN_RATE_10")
    age_20_rate: float | None = Field(default=None, alias="PPLTN_RATE_20")
    age_30_rate: float | None = Field(default=None, alias="PPLTN_RATE_30")
    age_40_rate: float | None = Field(default=None, alias="PPLTN_RATE_40")
    age_50_rate: float | None = Field(default=None, alias="PPLTN_RATE_50")
    age_60_rate: float | None = Field(default=None, alias="PPLTN_RATE_60")
    age_70_plus_rate: float | None = Field(default=None, alias="PPLTN_RATE_70")

    resident_rate: float | None = Field(default=None, alias="RESNT_PPLTN_RATE")
    non_resident_rate: float | None = Field(
        default=None, alias="NON_RESNT_PPLTN_RATE"
    )

    replacement_yn: Literal["Y", "N"] = Field(alias="REPLACE_YN")
    population_time: str = Field(alias="PPLTN_TIME")
    # 하위 2개는 예측 응답이 있는데 결과가 없거나 그 반대인 경우를 확인하기 위해 필드 보존
    forecast_yn: Literal["Y", "N"] = Field(alias="FCST_YN")
    forecasts: list[SeoulApiForecast] | None = Field(
        default=None, alias="FCST_PPLTN"
    )


# 최상위 JSON 전체 구조 검증용
class SeoulApiPopulationResponse(SeoulApiModel):
    populations: list[SeoulApiPopulation] = Field(
        default_factory=list,
        alias="SeoulRtd.citydata_ppltn",
    )
    result: SeoulApiResult = Field(alias="RESULT")


# MCP 용 구조, 기존 대문자 구성 API Y/N 등을 노출시키지 않음
class PopulationDemographics(BaseModel):
    male_rate: float | None = Field(default=None, ge=0, le=100)
    female_rate: float | None = Field(default=None, ge=0, le=100)
    age_0_to_10_rate: float | None = Field(default=None, ge=0, le=100)
    age_10_rate: float | None = Field(default=None, ge=0, le=100)
    age_20_rate: float | None = Field(default=None, ge=0, le=100)
    age_30_rate: float | None = Field(default=None, ge=0, le=100)
    age_40_rate: float | None = Field(default=None, ge=0, le=100)
    age_50_rate: float | None = Field(default=None, ge=0, le=100)
    age_60_rate: float | None = Field(default=None, ge=0, le=100)
    age_70_plus_rate: float | None = Field(default=None, ge=0, le=100)
    resident_rate: float | None = Field(default=None, ge=0, le=100)
    non_resident_rate: float | None = Field(default=None, ge=0, le=100)


# 혼잡도
class CongestionForecast(BaseModel):
    forecast_at: AwareDatetime 
    congestion_level: CongestionLevel
    population_min: int = Field(ge=0)
    population_max: int = Field(ge=0)


# 최종적으로 반환할 값
class CongestionSnapshot(BaseModel):
    area_name: str = Field(min_length=1)
    area_code: str = Field(min_length=1)

    congestion_level: CongestionLevel
    congestion_score: int = Field(ge=0, le=100)
    congestion_message: str

    population_min: int = Field(ge=0)
    population_max: int = Field(ge=0)

    observed_at: AwareDatetime
    fetched_at: AwareDatetime

    is_replacement_data: bool
    forecast_available: bool

    demographics: PopulationDemographics
    forecasts: list[CongestionForecast] = Field(default_factory=list)

    source: Literal["seoul_open_data"] = "seoul_open_data"


class LocationCongestionResult(BaseModel):
    poi_match: PoiMatch
    congestion: CongestionSnapshot


class NearbyCongestionResult(BaseModel):
    center_latitude: float = Field(ge=-90, le=90)
    center_longitude: float = Field(ge=-180, le=180)
    radius_meters: float = Field(ge=0)
    areas: list[LocationCongestionResult] = Field(default_factory=list)


# MCP TOOL SERVER 혼잡도
class CongestionToolResult(BaseModel):
    query_type: Literal["area", "location"] # 장소 조회, 좌표 조회인 지 구분지을 수 있는 Flag
    poi_match: PoiMatch | None = None # 좌표 조회 시 어떤 Poi 로 매핑됐는지 나타낸다.
    congestion: CongestionSnapshot # 최종 혼잡도 제공한다.
