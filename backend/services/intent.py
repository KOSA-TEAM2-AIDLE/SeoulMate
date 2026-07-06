"""API 명세서 3-5 'Intent 분류 기준', 'MCP 도구 선택 기준' 표 참고.

분류 우선순위: route_edit > route_multi > route_day > mcp/rag/both > LLM 폴백(chitchat)
"""
import json

from core.config import ANTHROPIC_API_KEY
from schemas.chat import ChatMessage, Intent

ROUTE_EDIT_KEYWORDS = [
    "빼줘", "바꿔줘", "수정", "다른 곳", "변경",
    "remove", "change", "replace", "edit",
]
ROUTE_MULTI_KEYWORDS = ["박", "여행 일정", "3박", "2박", "1박", "travel plan", "night"]
ROUTE_DAY_KEYWORDS = [
    "하루", "당일", "코스", "루트", "일정 짜",
    "one day", "day trip", "itinerary", "route",
]
RAG_KEYWORDS = [
    "추천", "조용", "분위기", "인스타", "데이트", "이색", "맛집",
    "recommend", "quiet", "cozy", "romantic", "cafe",
]
MCP_KEYWORDS = [
    "혼잡", "붐빔", "날씨", "비", "기온", "지하철", "교통", "행사", "축제", "지금", "오늘",
    "crowd", "weather", "transit", "event", "now", "today",
]

CONGESTION_KEYWORDS = ["혼잡", "붐빔", "사람 많아", "crowd", "busy"]
WEATHER_KEYWORDS = ["날씨", "비", "기온", "더위", "추위", "weather", "rain", "temperature"]
HOTEL_KEYWORDS = ["숙박", "호텔", "예약", "빈방", "hotel", "accommodation", "book", "reservation"]


def _contains_any(message: str, keywords: list[str]) -> bool:
    lowered = message.lower()
    return any(kw.lower() in lowered for kw in keywords)


def _history_has_route(history: list[ChatMessage]) -> bool:
    for msg in history:
        if msg.role != "assistant":
            continue
        try:
            parsed = json.loads(msg.content)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict) and parsed.get("type") == "route":
            return True
    return False


def classify_intent(message: str, lang: str, history: list[ChatMessage]) -> Intent:
    """history에 type: route 데이터가 있어야만 route_edit으로 분류됨 (10장 참고)."""
    if _contains_any(message, ROUTE_EDIT_KEYWORDS) and _history_has_route(history):
        return "route_edit"
    if _contains_any(message, ROUTE_MULTI_KEYWORDS):
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
    return "chitchat" if ANTHROPIC_API_KEY else "rag"


def pick_mcp_tool(message: str) -> str:
    """mcp/both intent일 때 get_congestion | get_weather | get_hotel_availability 중 선택.
    키워드 미감지 시 get_congestion이 기본값."""
    if _contains_any(message, WEATHER_KEYWORDS):
        return "get_weather"
    if _contains_any(message, HOTEL_KEYWORDS):
        return "get_hotel_availability"
    return "get_congestion"
