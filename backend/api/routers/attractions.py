"""현재 events API를 문화시설 API 호환 경로로 노출한다."""
from api.routers.events import router
__all__ = ["router"]

