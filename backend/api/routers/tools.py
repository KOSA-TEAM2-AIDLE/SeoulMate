"""API 명세서 3-2 GET /tools"""
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/tools")
def list_tools():
    raise HTTPException(status_code=501, detail="미구현")
