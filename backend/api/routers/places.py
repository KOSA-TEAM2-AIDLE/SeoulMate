"""API 명세서 3-3 GET /places (RAG 코퍼스 장소 목록)

이 엔드포인트는 RAG 코퍼스 확인용 디버깅/관리용으로만 사용
   
"""
from fastapi import APIRouter, HTTPException, Query
from schemas.common import Place

router = APIRouter()


@router.get("/places", response_model=list[Place])
def list_places(query: str = Query(...), lang: str = Query("ko")):
    raise HTTPException(status_code=501, detail="미구현")
