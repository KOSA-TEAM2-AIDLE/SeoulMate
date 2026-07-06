"""API 명세서 3-5 DayPlan/TimeSlot, 10장 route_edit 참고."""
from schemas.chat import ChatMessage, DayPlan
from schemas.common import ToolResult


def build_day_route(message: str, lang: str) -> tuple[list[DayPlan], list[ToolResult]]:
    """route_day: 1일 코스 추천."""
    raise NotImplementedError


def build_multi_route(message: str, lang: str) -> tuple[list[DayPlan], list[ToolResult]]:
    """route_multi: N박 여행 일정 추천."""
    raise NotImplementedError


def edit_route(
    message: str, lang: str, history: list[ChatMessage]
) -> tuple[list[DayPlan], list[ToolResult]]:
    """route_edit: history 마지막 route(type: route)를 파싱해 수정 반영."""
    raise NotImplementedError
