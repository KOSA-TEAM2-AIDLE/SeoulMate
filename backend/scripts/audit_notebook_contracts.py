"""프로젝트 Jupyter 노트북이 현재 백엔드 계약과 맞는지 검사한다."""

from __future__ import annotations

import ast
import json
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
NOTEBOOKS = {
    "weather": BACKEND / "weather_rag_manual_test.ipynb",
    "intent": BACKEND / "notebooks" / "SeoulMate_intent_langgraph_weather_mcp.ipynb",
    "rag_debug": BACKEND / "notebooks" / "SeoulMate_rag_mcp_debug.ipynb",
    "search_policy": BACKEND / "notebooks" / "SeoulMate_search_policy_test.ipynb",
    "structured_backend": BACKEND / "notebooks" / "SeoulMate_structured_rag_mcp_mock_domains_test.ipynb",
}

REQUIRED_TEXT = {
    "weather": ["services.weather", "services.weather_reranker"],
    "intent": [
        "class RouteRequest",
        "route_request: Optional[RouteRequest]",
        "RUN_LIVE_PARSER_MCP = False",
    ],
    "rag_debug": ["schemas.structured_query", "derive_source_mode"],
    "search_policy": ["schemas.structured_query", "services.query_policy"],
    "structured_backend": [
        "class RouteRequest",
        "route_request: Optional[RouteRequest]",
        "RUN_LIVE_PARSER_MCP = False",
    ],
}

FORBIDDEN_TEXT = {
    "intent": ["modify_route", "route_context", "current_route", "RouteOperation"],
    "structured_backend": [
        "modify_route", "route_context", "current_route", "RouteOperation",
    ],
}


def main() -> int:
    failures: list[str] = []
    for name, path in NOTEBOOKS.items():
        if not path.exists():
            failures.append(f"{name}: 파일 없음 - {path}")
            continue
        try:
            notebook = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"{name}: JSON 오류 - {exc}")
            continue

        source = "\n".join(
            "".join(cell.get("source", [])) for cell in notebook.get("cells", [])
        )
        for required in REQUIRED_TEXT[name]:
            if required not in source:
                failures.append(f"{name}: 최신 계약 누락 - {required}")
        for forbidden in FORBIDDEN_TEXT.get(name, []):
            if forbidden in source:
                failures.append(f"{name}: 제거되어야 할 Mock 계약 존재 - {forbidden}")

        for index, cell in enumerate(notebook.get("cells", [])):
            for output in cell.get("outputs", []):
                if output.get("output_type") == "error":
                    failures.append(
                        f"{name}: cell {index} 저장 오류 - "
                        f"{output.get('ename')}: {output.get('evalue')}"
                    )
            if cell.get("cell_type") != "code":
                continue
            code = "".join(cell.get("source", []))
            if any(line.lstrip().startswith(("%", "!")) for line in code.splitlines()):
                continue
            try:
                compile(
                    code,
                    f"{path}:cell{index}",
                    "exec",
                    flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
                )
            except SyntaxError as exc:
                failures.append(f"{name}: cell {index} 문법 오류 - {exc}")

        print(f"PASS | {name}: {path.name}")

    if failures:
        print("\nFAILURES")
        for failure in failures:
            print("-", failure)
        return 1
    print(f"\n전체 {len(NOTEBOOKS)}개 노트북 계약 감사 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
