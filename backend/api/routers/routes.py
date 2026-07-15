"""저장 루트 CRUD endpoint 스켈레톤.

루트 생성·수정은 현재 POST /chat SSE에서 동작한다. 팀의 영속화 API 명세가 확정되면
이 router에 저장/조회/삭제 endpoint를 추가하고 application.route만 호출한다.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/routes", tags=["routes"])

__all__ = ["router"]

