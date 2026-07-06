"""API 명세서 3-5, 10장 POST /chat (SSE 스트리밍)

분류 우선순위: route_edit > route_multi > route_day > mcp/rag/both > LLM 폴백(chitchat)
route_edit은 history에 type: route 데이터가 있을 때만 분류됨.
"""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from schemas.chat import ChatDone, ChatMetaPlaces, ChatMetaRoute, ChatRequest, ChatToken
from services.intent import classify_intent

router = APIRouter()

ROUTE_INTENTS = {"route_day", "route_multi", "route_edit"}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream(body: ChatRequest):
    intent = classify_intent(body.message, body.lang, body.history)

    if intent in ROUTE_INTENTS:
        meta = ChatMetaRoute(intent=intent, days=[], total_days=0, total_places=0)
    else:
        meta = ChatMetaPlaces(intent=intent)
    yield _sse(meta.model_dump())

    # TODO: services.rag / services.mcp_tools / services.route_builder 실제 연동 전까지
    #       임시 안내 문구를 토큰 단위로 스트리밍
    placeholder = f"[{intent}] RAG/MCP 연동 전 임시 응답입니다."
    for word in placeholder.split(" "):
        yield _sse(ChatToken(text=word + " ").model_dump())

    yield _sse(ChatDone().model_dump())


@router.post("/chat")
async def chat(body: ChatRequest):
    return StreamingResponse(_stream(body), media_type="text/event-stream")
