import asyncio
import json
import sys
from playwright.async_api import async_playwright


async def scrape_booking_live(
    location: str, checkin: str, checkout: str, adults: str = "2"
):
    """Booking.com에서 입력받은 조건으로 실시간 호텔 방과 가격을 스크레이핑합니다."""
    url = (
        f"https://www.booking.com/searchresults.html"
        f"?ss={location}&checkin={checkin}&checkout={checkout}&group_adults={adults}"
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector('[data-testid="property-card"]', timeout=15000)
            cards = await page.query_selector_all('[data-testid="property-card"]')

            results = []
            for card in cards[:20]:
                title_el = await card.query_selector('[data-testid="title"]')
                title = await title_el.inner_text() if title_el else "이름 없음"

                price_el = await card.query_selector(
                    '[data-testid="price-and-discounted-price"]'
                )
                if not price_el:
                    price_el = await card.query_selector(
                        '[data-testid="price-display-raw"]'
                    )
                price = await price_el.inner_text() if price_el else "가격 정보 없음"
                price = " ".join(price.split())

                rating_el = await card.query_selector('[data-testid="review-score"]')
                rating = (
                    (await rating_el.inner_text()).split("\n")[0]
                    if rating_el
                    else "평점 없음"
                )

                link_el = await card.query_selector('[data-testid="title-link"]')
                link = await link_el.get_attribute("href") if link_el else "#"
                if link and link.startswith("/"):
                    link = "https://www.booking.com" + link

                results.append(
                    {
                        "hotel_name": title.strip(),
                        "live_price": price.strip(),
                        "live_rating": rating.strip(),
                        "booking_url": link.strip(),
                    }
                )

            return {"status": "success", "data": results}

        except Exception as e:
            return {"status": "error", "message": str(e), "data": []}
        finally:
            await browser.close()


def main(location: str, checkin: str, checkout: str, adults: str = "2"):
    """agent_runner.py가 동기 방식으로 직접 호출하는 진입점 함수"""
    return asyncio.run(scrape_booking_live(location, checkin, checkout, adults))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(1)
    print(
        json.dumps(
            main(sys.argv[1], sys.argv[2], sys.argv[3]), ensure_ascii=False, indent=2
        )
    )
