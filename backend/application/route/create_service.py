"""검색 완료된 슬롯 후보로 하나의 확정 루트를 생성한다."""

import asyncio

from application.route.route_planner import generate_route_plan
from schemas.route_planner import ConfirmedRoutePlan, RoutePlannerInput


class RouteCreateService:
    implemented = True

    async def create(self, planner_input: RoutePlannerInput) -> ConfirmedRoutePlan:
        return await asyncio.to_thread(generate_route_plan, planner_input)


__all__ = ["RouteCreateService"]

