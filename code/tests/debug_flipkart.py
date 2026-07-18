from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

TEST_URL = "https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itmbf14ef54f645d"

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
    page.goto(TEST_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    # Scroll to trigger lazy load
    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    page.wait_for_timeout(1500)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2000)

    # Find anything with a number near the word Ratings
    print("\n── All elements containing 'Rating' ───────────")
    for el in page.query_selector_all("*"):
        try:
            text = el.inner_text().strip()
            if "ating" in text and len(text) < 80 and any(c.isdigit() for c in text):
                tag = el.evaluate("el => el.tagName")
                cls = el.get_attribute("class") or ""
                print(f"  <{tag} class='{cls[:60]}'> {text!r}")
        except Exception:
            continue

    context.close()
    browser.close()