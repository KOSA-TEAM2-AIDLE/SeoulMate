from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()