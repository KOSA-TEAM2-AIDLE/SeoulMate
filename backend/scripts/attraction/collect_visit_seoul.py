"""Visit Seoul API 수집기. 명시적으로 실행할 때만 외부 API를 호출한다."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx


class VisitSeoulClient:
    BASE_URL = "https://api-call.visitseoul.net/api/v1"

    def __init__(self, api_key: str, *, http_client: Any | None = None, timeout: float = 20.0) -> None:
        if not api_key.strip():
            raise ValueError("VISIT_SEOUL_API_KEY가 필요합니다.")
        self.api_key = api_key
        self.http_client = http_client or httpx.Client()
        self.timeout = timeout

    def fetch_page(self, path: str, params: dict[str, object]) -> dict[str, Any]:
        response = self.http_client.get(
            f"{self.BASE_URL}/{path.lstrip('/')}",
            headers={"VISITSEOUL-API-KEY": self.api_key}, params=params, timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


def main() -> None:
    key = os.getenv("VISIT_SEOUL_API_KEY", "")
    client = VisitSeoulClient(key)
    payload = client.fetch_page("contents", {"langCode": "ko", "page": 1, "size": 100})
    output = Path("data/attraction/raw/visit_seoul_sample.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
