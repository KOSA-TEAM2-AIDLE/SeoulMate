"""API 명세서 3-4 POST /actions"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from schemas.common import ToolResult

router = APIRouter()


class ActionRequest(BaseModel):
    tool_name: str  # get_congestion | get_weather | get_hotel_availability
    params: dict


@router.post("/actions", response_model=ToolResult)
def call_action(body: ActionRequest):
    raise HTTPException(status_code=501, detail="미구현")
