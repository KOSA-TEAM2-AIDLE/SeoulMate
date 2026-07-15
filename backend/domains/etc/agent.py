from domains.common.agent import TemporaryDomainAgentBase


class EtcAgent(TemporaryDomainAgentBase):
    """기타 도메인의 전체 요청을 처리할 임시 에이전트."""

    domain = "etc"


__all__ = ["EtcAgent"]
