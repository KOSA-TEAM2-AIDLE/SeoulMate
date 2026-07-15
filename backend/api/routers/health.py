"""GET /health"""

from fastapi import APIRouter

from core.config import LLM_MODE, SEOUL_API_ENABLED, WEATHER_API_ENABLED


router = APIRouter()


@router.get("/health")
def health_check():
    return {
        "ok": True,
        "modes": {
            "seoul_api": "live" if SEOUL_API_ENABLED else "mock",
            "weather": "live" if WEATHER_API_ENABLED else "disabled",
            "llm": LLM_MODE,
        },
    }
