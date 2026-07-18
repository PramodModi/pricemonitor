from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from app.utils.logging import configure_logging
from app.scrapers.flipkart import FlipkartScraper

configure_logging("INFO")

TEST_URL = "https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itmbf14ef54f645d"

scraper = FlipkartScraper()

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context(
        locale="en-IN",
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()
    Stealth().apply_stealth_sync(page)

    try:
        result = scraper.extract(page, TEST_URL)
        print("\n── Scrape Result ──────────────────────────────")
        print(f"PID:           {result.marketplace_product_id}")
        print(f"Name:          {result.name}")
        print(f"Price:         ₹{result.current_price}")
        print(f"Available:     {result.availability}")
        print(f"Rating:        {result.rating}")
        print(f"Review count:  {result.review_count}")
        print(f"Seller:        {result.seller}")
        print(f"Image URL:     {result.image_url}")
    except Exception as e:
        print(f"\n── Error ──────────────────────────────────────")
        print(f"{type(e).__name__}: {e}")
    finally:
        context.close()
        browser.close()