"""공통 설정. API 명세서 1장 참고 (source: live/mock 판단에 사용되는 모드 플래그 포함)."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # 설정 파일 없이 환경변수만 사용하는 실행 환경
    load_dotenv = None

if load_dotenv:
    load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

# /health 응답의 modes 필드 
SEOUL_API_ENABLED = bool(os.getenv("SEOUL_OPEN_API_KEY"))
WEATHER_API_ENABLED = bool(os.getenv("KMA_API_KEY"))
LLM_MODE = os.getenv("LLM_MODE", "openai-api")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")
OPENAI_EMBED_DIM = int(os.getenv("OPENAI_EMBED_DIM", "1536"))

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KMA_API_KEY = os.getenv("KMA_API_KEY")
WEATHER_CACHE_TTL_SECONDS = int(os.getenv("WEATHER_CACHE_TTL_SECONDS", "600"))
WEATHER_RERANK_WEIGHT = float(os.getenv("WEATHER_RERANK_WEIGHT", "0.10"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5433")),
    "dbname": os.getenv("DB_NAME", "seoulmate"),
    "user": os.getenv("DB_USER", "seoulmate"),
    "password": os.getenv("DB_PASSWORD", "1234"),
}
