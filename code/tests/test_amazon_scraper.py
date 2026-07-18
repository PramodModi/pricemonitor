from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from app.utils.logging import configure_logging
from app.scrapers.amazon import AmazonScraper

configure_logging("INFO")

# Swap this URL for any Amazon India product you want to test with
TEST_URL = "https://www.amazon.in/Apple-iPhone-15-128-GB/dp/B0CHX1W1XY"
#TEST_URL = "https://www.amazon.in/Lifelong-Treadmill-Home-Motorized-Bluetooth/dp/B0D3V96ZK3/?_encoding=UTF8&pd_rd_w=qX8G4&content-id=amzn1.sym.340182bc-8d5c-49c7-8b69-c0403f7ba3a7%3Aamzn1.symc.752cde0b-d2ce-4cce-9121-769ea438869e&pf_rd_p=340182bc-8d5c-49c7-8b69-c0403f7ba3a7&pf_rd_r=B7XV6X8TMTED2PHPR4HM&pd_rd_wg=z4iOb&pd_rd_r=931bd3b3-a556-46ad-a427-2d6f9dadae32&ref_=pd_hp_d_atf_ci_mcx_mr_"

scraper = AmazonScraper()

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False)  # headless=False so you can watch it
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

    result = scraper.extract(page, TEST_URL)

    context.close()
    browser.close()

print("\n── Scrape Result ──────────────────────────────")
print(f"ASIN:          {result.marketplace_product_id}")
print(f"Name:          {result.name}")
print(f"Brand:         {result.brand}")
print(f"Price:         ₹{result.current_price}")
print(f"Available:     {result.availability}")
print(f"Rating:        {result.rating}")
print(f"Review count:  {result.review_count}")
print(f"Seller:        {result.seller}")
print(f"Image URL:     {result.image_url}")