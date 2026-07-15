from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent # backend 폴더 위치 지정
DATA_DIR = BASE_DIR / "data"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file = BASE_DIR / ".env",
        env_file_encoding = "utf-8",
        extra="ignore", # Settings 에 지정하지 않은 값이 있을 때 에러 처리 방식
    )

    allowed_origins : str = "http://localhost:5173"
    
    # SecretStr : 출력시 자연어로 나오는게 아니라, ***** 형태로 마스킹 되어 나옴
    seoul_open_api_key : SecretStr | None = None 
    seoul_api_base_url: str = "http://openapi.seoul.go.kr:8088"
    seoul_api_timeout_seconds : float = 5.0

    congestion_cache_ttl_seconds: int = 300

    kakao_rest_api_key: SecretStr | None = None
    kakao_local_api_base_url: str = "https://dapi.kakao.com"
    kakao_local_api_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
    )
    kakao_place_result_limit: int = Field(
        default=5,
        ge=1,
        le=15,
    )
    kakao_place_cache_ttl_seconds: int = Field(
        default=86400,
        ge=0,
    )

    public_data_service_key: SecretStr | None = None
    storage_locker_api_base_url: str = (
        "https://apis.data.go.kr/B551982/psl_v2"
    )
    storage_locker_api_timeout_seconds: float = Field(default=10.0, gt=0)
    storage_locker_api_page_size: int = Field(default=1000, ge=1, le=10000)
    storage_locker_cache_ttl_seconds: int = Field(default=60, ge=0)

    mcp_server_url: str = "http://localhost:8001/mcp"
    mcp_server_host: str = "127.0.0.1"
    mcp_server_port: int = 8001

    kma_api_key: SecretStr | None = None 
    anthropic_api_key: SecretStr | None = None
    llm_mode: str = "anthropic-api"


    # 환경변수 및 설정값 정의
    @property
    def allowed_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]

    @property
    def seoul_api_enabled(self) -> bool:
        return self.seoul_open_api_key is not None

    @field_validator("kakao_local_api_base_url")
    @classmethod
    def validate_kakao_local_api_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError(
                "Kakao Local API 기본 URL은 비어 있을 수 없습니다."
            )
        return normalized

    @property
    def kakao_local_api_enabled(self) -> bool:
        if self.kakao_rest_api_key is None:
            return False
        return bool(
            self.kakao_rest_api_key.get_secret_value().strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
