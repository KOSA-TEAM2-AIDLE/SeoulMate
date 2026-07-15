from domains.common.agent import TemporaryDomainAgentBase


class RestaurantAgent(TemporaryDomainAgentBase):
    """식당 도메인의 전체 요청을 처리할 임시 에이전트."""

    domain = "restaurant"


__all__ = ["RestaurantAgent"]
