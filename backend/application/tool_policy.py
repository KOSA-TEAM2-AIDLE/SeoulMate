"""공통 도구 호출 여부. MCP는 사실을 제공하고 도메인 재랭커가 점수를 정한다."""

from services.source_router import normalize_source_mode


def requested_contexts(source_mode: str, domain: str) -> tuple[str, ...]:
    mode = normalize_source_mode(source_mode)
    if mode != "rag_mcp":
        return ()
    # Attraction 혼잡도는 검색 중심지가 아니라 정적 후보별 좌표로
    # 조회해야 하므로 AttractionCongestionReranker에서 따로 처리한다.
    if domain in {"restaurant", "cafe", "accommodation"}:
        return ("weather",)
    return ()


__all__ = ["requested_contexts"]
