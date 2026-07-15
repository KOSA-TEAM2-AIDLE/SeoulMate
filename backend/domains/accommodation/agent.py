from domains.common.agent import TemporaryDomainAgentBase


class AccommodationAgent(TemporaryDomainAgentBase):
    """숙박 도메인의 전체 요청을 처리할 임시 에이전트."""

    domain = "accommodation"


__all__ = ["AccommodationAgent"]
