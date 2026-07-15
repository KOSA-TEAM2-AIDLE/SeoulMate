from domains.common.agent import TemporaryDomainAgentBase


class AttractionAgent(TemporaryDomainAgentBase):
    """명소 도메인의 전체 요청을 처리할 임시 에이전트."""

    domain = "attraction"


__all__ = ["AttractionAgent"]
