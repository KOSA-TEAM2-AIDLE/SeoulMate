"""Google Maps 리뷰 수집 보조기.

Playwright가 설치된 환경에서만 실행하며, 대상 CSV를 명시적으로 전달받는다.
"""
from __future__ import annotations

import asyncio
import csv
from pathlib import Path


async def collect_reviews(target_csv: Path, output_csv: Path, *, limit_per_place: int = 10) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError as error:
        raise RuntimeError("리뷰 수집은 선택 의존성 playwright가 필요합니다.") from error
    
    # 현재는 데이터 수집을 기존 .csv 파일을 기반으로 진행
    with target_csv.open(encoding="utf-8-sig", newline="") as source:
        targets = list(csv.DictReader(source))
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    
    with output_csv.open("w", encoding="utf-8-sig", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=["place_key", "review_id", "rating", "text", "crawl_status"])
        writer.writeheader()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False)
            page = await browser.new_page()
            for target in targets:
                query = f"{target['name']} {target['road_address']}"
                await page.goto(f"https://www.google.com/maps/search/{query}", wait_until="domcontentloaded")
                cards = page.locator("div[data-review-id]")
                for index in range(min(await cards.count(), limit_per_place)):
                    card = cards.nth(index)
                    writer.writerow({"place_key": target["place_key"], "review_id": await card.get_attribute("data-review-id"), "rating": "", "text": (await card.inner_text()).strip(), "crawl_status": "success"})
            await browser.close()


if __name__ == "__main__":
    raise SystemExit("collect_reviews()를 호출하는 전용 실행 명령을 추가한 뒤 사용하세요.")
