"""API 명세서 3-5 'Intent 분류 기준', 'MCP 도구 선택 기준' 표 참고.

분류 우선순위: route_multi > route_day > mcp/rag/both > LLM 폴백(chitchat)
"""
import re

from core.config import OPENAI_API_KEY
from schemas.chat import ChatMessage, Intent

ROUTE_MULTI_KEYWORDS = ["여행 일정", "travel plan", "multi-day itinerary"]
ROUTE_DAY_KEYWORDS = [
    "하루", "당일", "코스", "루트", "일정 짜",
    "one day", "day trip", "itinerary", "route",
]
RAG_KEYWORDS = [
    "추천", "조용", "분위기", "인스타", "데이트", "이색", "맛집",
    "가기 좋은", "식당", "음식", "먹을", "먹기",
    "recommend", "quiet", "cozy", "romantic", "cafe", "restaurant", "food", "good place",
]
MCP_KEYWORDS = [
    "혼잡", "붐빔", "날씨", "비", "기온", "지하철", "교통", "행사", "축제", "지금", "오늘",
    "내일", "모레", "저녁", "점심",
    "crowd", "weather", "transit", "event", "now", "today", "tomorrow", "tonight", "lunch", "dinner",
]

CONGESTION_KEYWORDS = ["혼잡", "붐빔", "사람 많아", "crowd", "busy"]
WEATHER_KEYWORDS = ["날씨", "비", "기온", "더위", "추위", "weather", "rain", "temperature"]
HOTEL_KEYWORDS = ["숙박", "호텔", "예약", "빈방", "hotel", "accommodation", "book", "reservation"]


def _contains_any(message: str, keywords: list[str]) -> bool:
    lowered = message.lower()
    return any(kw.lower() in lowered for kw in keywords)


def classify_intent(message: str, lang: str, history: list[ChatMessage]) -> Intent:
    """사용자 문장을 최초 루트 생성·추천·도구·일반 대화로 분류한다."""
    has_trip_duration = bool(
        re.search(r"\d+\s*박", message)
        or re.search(r"\b\d+\s*nights?\b", message.lower())
    )
    if has_trip_duration or _contains_any(message, ROUTE_MULTI_KEYWORDS):
        return "route_multi"
    if _contains_any(message, ROUTE_DAY_KEYWORDS):
        return "route_day"

    has_rag = _contains_any(message, RAG_KEYWORDS)
    has_mcp = _contains_any(message, MCP_KEYWORDS)
    if has_rag and has_mcp:
        return "both"
    if has_mcp:
        return "mcp"
    if has_rag:
        return "rag"

    # 키워드 미감지: LLM이 직접 대화(chitchat)로 응답. LLM 키 없으면 rag로 폴백.
    return "chitchat" if OPENAI_API_KEY else "rag"


def pick_mcp_tool(message: str) -> str:
    """mcp/both intent일 때 get_congestion | get_weather | get_hotel_availability 중 선택.
    키워드 미감지 시 get_congestion이 기본값."""
    if _contains_any(message, WEATHER_KEYWORDS):
        return "get_weather"
    if _contains_any(message, HOTEL_KEYWORDS):
        return "get_hotel_availability"
    return "get_congestion"
