"""API 명세서 3-1 GET /health"""
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/health")
def health_check():
    raise HTTPException(status_code=501, detail="미구현")
