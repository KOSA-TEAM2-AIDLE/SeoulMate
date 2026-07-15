from __future__ import annotations

import asyncio

from domains.common.agent import DomainAgent
from schemas.structured_query import TaskDomain
from schemas.travel_query_api import (
    DomainAgentDispatchResult,
    TravelQueryApiResponse,
)


class DomainAgentRegistry:
    def __init__(self, agents: list[DomainAgent] | None = None) -> None:
        self._agents: dict[TaskDomain, DomainAgent] = {}
        for agent in agents or []:
            self.register(agent)

    def register(self, agent: DomainAgent) -> None:
        if agent.domain in self._agents:
            raise ValueError(f"이미 등록된 도메인 에이전트입니다: {agent.domain}")
        self._agents[agent.domain] = agent

    def get(self, domain: TaskDomain) -> DomainAgent:
        try:
            return self._agents[domain]
        except KeyError as exc:
            raise LookupError(f"등록되지 않은 도메인 에이전트입니다: {domain}") from exc


def build_temporary_agent_registry() -> DomainAgentRegistry:
    from domains.accommodation.agent import AccommodationAgent
    from domains.attraction.agent import AttractionAgent
    from domains.cafe.agent import CafeAgent
    from domains.etc.agent import EtcAgent
    from domains.restaurant.agent import RestaurantAgent

    return DomainAgentRegistry([
        RestaurantAgent(),
        CafeAgent(),
        AccommodationAgent(),
        AttractionAgent(),
        EtcAgent(),
    ])


class ReadyDomainAgentDispatcher:
    def __init__(self, registry: DomainAgentRegistry | None = None) -> None:
        self.registry = registry or build_temporary_agent_registry()

    async def dispatch(
        self,
        response: TravelQueryApiResponse,
    ) -> list[DomainAgentDispatchResult]:
        if response.status != "ready" or response.structured_query is None:
            return []

        # Task 순서를 유지하면서 중복 도메인을 제거한다.
        domains = list(
            dict.fromkeys(task.domain for task in response.structured_query.tasks)
        )
        return list(
            await asyncio.gather(
                *[
                    self.registry.get(domain).execute(response)
                    for domain in domains
                ]
            )
        )


__all__ = [
    "DomainAgent",
    "DomainAgentRegistry",
    "ReadyDomainAgentDispatcher",
    "build_temporary_agent_registry",
]
