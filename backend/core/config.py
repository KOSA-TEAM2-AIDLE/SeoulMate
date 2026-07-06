"""공통 설정. API 명세서 1장 참고 (source: live/mock 판단에 사용되는 모드 플래그 포함)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

# /health 응답의 modes 필드 
SEOUL_API_ENABLED = bool(os.getenv("SEOUL_OPEN_API_KEY"))
WEATHER_API_ENABLED = bool(os.getenv("KMA_API_KEY"))
LLM_MODE = os.getenv("LLM_MODE", "anthropic-api")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
