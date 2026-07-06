"""Anthropic API 래퍼. chitchat 폴백 응답 및 추천 이유(reason) 생성용 스트리밍."""
from typing import AsyncIterator
from schemas.chat import ChatMessage


async def stream_chat_response(
    message: str, lang: str, history: list[ChatMessage]
) -> AsyncIterator[str]:
    """LLM 응답을 텍스트 청크 단위로 스트리밍 (SSE type: token 이벤트에 사용)."""
    raise NotImplementedError
    yield ""  # pragma: no cover - async generator 형태 유지용
