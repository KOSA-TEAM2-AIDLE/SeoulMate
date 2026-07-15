"""팀원 구현용 Congestion MCP Provider 스켈레톤."""

from domains.common.exceptions import DomainNotImplementedError
from integrations.mcp.base_client import ContextRequest, ContextResult


class CongestionMCPProvider:
    name = "congestion"
    implemented = False

    async def get_context(self, request: ContextRequest) -> ContextResult:
        raise DomainNotImplementedError(
            "혼잡도 MCP가 아직 구현되지 않았습니다. area code, 관측 시각, "
            "freshness, congestion tag를 반환하도록 구현하세요."
        )


__all__ = ["CongestionMCPProvider"]

