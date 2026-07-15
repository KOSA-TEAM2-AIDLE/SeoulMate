"""공통 도구 호출 여부. MCP는 사실을 제공하고 도메인 재랭커가 점수를 정한다."""

from services.source_router import normalize_source_mode


def requested_contexts(source_mode: str, domain: str) -> tuple[str, ...]:
    mode = normalize_source_mode(source_mode)
    if mode != "rag_mcp":
        return ()
    # Weather는 현재 구현됨. Congestion은 Registry에 스켈레톤으로 존재하되
    # 구현 완료 후 이 정책에 추가한다.
    if domain in {"restaurant", "cafe", "accommodation", "attraction"}:
        return ("weather",)
    return ()


__all__ = ["requested_contexts"]

