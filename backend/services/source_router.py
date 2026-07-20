"""첫 번째 GPT가 최종 답변에 사용할 데이터 소스를 결정한다."""

from __future__ import annotations

import asyncio
import json
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from core.config import OPENAI_API_KEY, OPENAI_CHAT_MODEL
from schemas.chat import ChatMessage
from models.intent.classifier import classify_intent


SourceMode = Literal["RAG_ONLY", "RAG_MCP", "MCP_ONLY", "CHITCHAT"]
CanonicalSourceMode = Literal["rag_only", "rag_mcp", "mcp_only", "general"]


class SourceDecision(BaseModel):
    mode: SourceMode
    reason: str = Field(description="선택 이유를 한 문장으로 설명")


ROUTER_INSTRUCTIONS = """너는 SeoulMate의 데이터 소스 라우터다.
답변을 직접 작성하지 말고 아래 mode 중 정확히 하나만 선택한다.

- RAG_ONLY: 장소·숙박·카페·문화시설·식당 추천/검색이 필요하지만 현재 또는 미래 날씨는 필요하지 않다.
- RAG_MCP: 장소 추천/검색과 현재·미래 날씨가 모두 필요하다. 방문 날짜·시간이 명시되었거나 비·눈·기온·야외활동처럼 날씨가 추천 품질에 영향을 준다.
- MCP_ONLY: 장소 추천 없이 날씨, 비, 눈, 기온, 바람 등 실시간/예보 정보만 묻는다.
- CHITCHAT: 장소 검색도 날씨 조회도 필요 없는 일반 대화다.

중요:
1. '내일 갈 카페 추천'처럼 추천과 방문 시점이 함께 있으면 RAG_MCP다.
2. '조용한 카페 추천'처럼 시점·날씨가 없으면 RAG_ONLY다.
3. '내일 서울 날씨 어때?'는 MCP_ONLY다.
4. 사용자가 단순히 '오늘'이라는 단어를 썼더라도 장소 추천과 무관하면 의미를 보고 판단한다.
5. 현재 연결된 MCP는 날씨 도구뿐이다."""


def _fallback_decision(message: str, lang: str, history: list[ChatMessage]) -> SourceDecision:
    intent = classify_intent(message, lang, history)
    lowered = message.lower()
    explicit_weather = any(
        word in lowered
        for word in (
            "날씨",
            "비",
            "눈",
            "기온",
            "온도",
            "더위",
            "추위",
            "바람",
            "강풍",
            "weather",
            "rain",
            "snow",
            "temperature",
            "wind",
            "hot",
            "cold",
        )
    )
    if intent == "mcp" and not explicit_weather:
        intent = "chitchat"
    mapping: dict[str, SourceMode] = {
        "rag": "RAG_ONLY",
        "both": "RAG_MCP",
        "mcp": "MCP_ONLY",
        "chitchat": "CHITCHAT",
    }
    return SourceDecision(
        mode=mapping.get(intent, "CHITCHAT"),
        reason="GPT 소스 라우터 실패로 키워드 안전 폴백을 사용했습니다.",
    )


def _decide_sync(message: str, lang: str, history: list[ChatMessage]) -> SourceDecision:
    if not OPENAI_API_KEY:
        return _fallback_decision(message, lang, history)
    history_payload = [item.model_dump() for item in history[-6:]]
    try:
        response = OpenAI(api_key=OPENAI_API_KEY).responses.parse(
            model=OPENAI_CHAT_MODEL,
            instructions=ROUTER_INSTRUCTIONS,
            input=json.dumps(
                {
                    "user_query": message,
                    "language": lang,
                    "recent_history": history_payload,
                },
                ensure_ascii=False,
            ),
            text_format=SourceDecision,
            max_output_tokens=300,
        )
        if response.output_parsed is None:
            raise RuntimeError("GPT 소스 라우터가 구조화 결과를 반환하지 않았습니다.")
        return response.output_parsed
    except Exception:
        return _fallback_decision(message, lang, history)


async def decide_source_mode(
    message: str,
    lang: str,
    history: list[ChatMessage],
) -> SourceDecision:
    """이벤트 루프를 막지 않고 GPT 구조화 라우팅을 수행한다."""
    return await asyncio.to_thread(_decide_sync, message, lang, history)


def normalize_source_mode(mode: str) -> CanonicalSourceMode:
    """고정 LangGraph 계약의 소문자 모드로 통일하되 기존 대문자 호출도 호환한다."""
    normalized = str(mode).strip().lower()
    aliases: dict[str, CanonicalSourceMode] = {
        "rag_only": "rag_only",
        "rag_mcp": "rag_mcp",
        "mcp_only": "mcp_only",
        "chitchat": "general",
        "general": "general",
    }
    if normalized not in aliases:
        raise ValueError(f"지원하지 않는 source_mode입니다: {mode}")
    return aliases[normalized]


def mode_to_intent(mode: str) -> Literal["rag", "both", "mcp", "chitchat"]:
    canonical = normalize_source_mode(mode)
    return {
        "rag_only": "rag",
        "rag_mcp": "both",
        "mcp_only": "mcp",
        "general": "chitchat",
    }[canonical]


__all__ = [
    "CanonicalSourceMode",
    "SourceDecision",
    "SourceMode",
    "decide_source_mode",
    "mode_to_intent",
    "normalize_source_mode",
]
