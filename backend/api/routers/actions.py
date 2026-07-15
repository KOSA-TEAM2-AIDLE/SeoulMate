"""API 명세서 3-4 POST /actions"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from schemas.common import ToolResult
from services.mcp_tools import call_tool

router = APIRouter()


class ActionRequest(BaseModel):
    tool_name: str  # get_congestion | get_weather | get_hotel_availability
    params: dict


@router.post("/actions", response_model=ToolResult)
def call_action(body: ActionRequest):
    result = call_tool(body.tool_name, body.params)
    if not result.ok and result.error == "지원하지 않는 도구입니다.":
        raise HTTPException(status_code=400, detail=result.error)
    return result
