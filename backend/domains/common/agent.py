from __future__ import annotations

from typing import Protocol

from schemas.structured_query import TaskDomain
from schemas.travel_query_api import (
    DomainAgentDispatchResult,
    TravelQueryApiResponse,
)


class DomainAgent(Protocol):
    domain: TaskDomain

    async def execute(
        self,
        response: TravelQueryApiResponse,
    ) -> DomainAgentDispatchResult: ...


class TemporaryDomainAgentBase:
    """실제 도메인 에이전트가 구현될 때까지 공통 수신 결과를 반환한다."""

    domain: TaskDomain

    async def execute(
        self,
        response: TravelQueryApiResponse,
    ) -> DomainAgentDispatchResult:
        query = response.structured_query
        task_ids = (
            [task.task_id for task in query.tasks if task.domain == self.domain]
            if query is not None
            else []
        )
        return DomainAgentDispatchResult(
            domain=self.domain,
            task_ids=task_ids,
            assistant_message=(
                f"{self.domain} 에이전트가 아직 구현되지 않아 "
                f"{len(task_ids)}개 Task의 전체 structured_query를 임시로 수신했습니다."
            ),
        )


__all__ = ["DomainAgent", "TemporaryDomainAgentBase"]
