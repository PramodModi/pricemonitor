"""
run_test.py — local CLI to test scraper_v2 against real URLs.

Usage:
    cd code
    python -m scraper_v2.run_test https://www.amazon.in/dp/B09XYZ12345
    python -m scraper_v2.run_test https://www.flipkart.com/product/p/ABCDEF
    python -m scraper_v2.run_test https://www.amazon.in/dp/B09XYZ --verbose
    python -m scraper_v2.run_test https://www.amazon.in/dp/B09XYZ --no-headless  # open browser window
    python -m scraper_v2.run_test https://www.amazon.in/dp/B09XYZ --dump-html          # write raw HTML to /tmp/amazon_dump.html
    python -m scraper_v2.run_test <any-url> --inspect-html                           # inspect last dump for selectors
    python -m scraper_v2.run_test <any-url> --inspect-html /path/to/file.html        # inspect specific dump

No DB required. Diagnostics printed to stdout.
Playwright must be installed: playwright install chromium
"""

from __future__ import annotations

import sys
import json
from dataclasses import asdict
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from app.scraper_v2.scrapers.generic_scraper import GenericScraper
from app.scraper_v2.scrapers.registry import get_config_for_domain, registered_platforms
from app.scraper_v2.core.exceptions import UnsupportedPlatformError


def run(url: str, verbose: bool = False, headless: bool = True, dump_html: bool = False, use_firefox: bool = False) -> None:
    domain = urlparse(url).netloc.lower().removeprefix("www.")

    try:
        config = get_config_for_domain(domain)
    except UnsupportedPlatformError:
        print(f"\n❌  Unsupported domain: {domain}")
        print(f"    Registered portals: {registered_platforms()}")
        print(f"    Add '{domain}' to scraper_v2/scrapers/portals.yaml to support it.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Portal   : {config.name}")
    print(f"  URL      : {url}")
    print(f"  Selectors: {len(config.price_selectors)}")
    print(f"  Hook     : {config.pre_extract_hook or 'none'}")
    print(f"{'='*60}\n")

    scraper = GenericScraper()

    with sync_playwright() as pw:
        # Use browser engine from portal config (firefox for Myntra, chromium default)
        browser_engine = config.browser if hasattr(config, "browser") else "chromium"
        if use_firefox or browser_engine == "firefox":
            browser = pw.firefox.launch(headless=headless)
            print(f"  Browser  : Firefox (portal={config.name})")
        else:
            browser = pw.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-http2",
                ],
            )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Encoding": "gzip, deflate, br",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            },
        )
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        if dump_html:
            # Navigate manually so we can inspect selectors before scraping
            # Try domcontentloaded first; fall back to "commit" for portals
            # like Myntra that block headless at TLS level
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except Exception:
                page.goto(url, wait_until="commit", timeout=20000)
            html = page.content()
            dump_path = "/tmp/amazon_dump.html"
            with open(dump_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"\n[DUMP] Page HTML written to {dump_path}")
            print(f"[DUMP] Page title: {page.title()!r}")
            print(f"[DUMP] Final URL : {page.url}")
            print(f"[DUMP] HTML size : {len(html):,} bytes")

            # Probe every selector we rely on so failures are visible instantly
            print("\n[DUMP] Selector probe:")
            # JSON-LD content (first script block)
            ld_scripts = page.query_selector_all("script[type='application/ld+json']")
            if ld_scripts:
                import json as _json
                for i, s in enumerate(ld_scripts[:3]):
                    try:
                        ld = _json.loads(s.inner_text())
                        print(f"  JSON-LD [{i}]: type={ld.get('@type')} price={ld.get('offers', {}).get('price') if isinstance(ld.get('offers'), dict) else [o.get('price') for o in ld.get('offers', [])][:2]}")
                    except Exception as e:
                        print(f"  JSON-LD [{i}]: parse error — {e}")

            probes = [
                # Meta tags (using query_selector — no timeout)
                ("meta product:price:amount @content",  lambda: (lambda e: e.get_attribute("content") if e else None)(page.query_selector("meta[property='product:price:amount']"))),
                ("meta og:price:amount @content",       lambda: (lambda e: e.get_attribute("content") if e else None)(page.query_selector("meta[property='og:price:amount']"))),
                ("meta og:title @content",              lambda: (lambda e: e.get_attribute("content")[:70] if e else None)(page.query_selector("meta[property='og:title']"))),
                ("meta og:image @content",              lambda: (lambda e: e.get_attribute("content")[:60] if e else None)(page.query_selector("meta[property='og:image']"))),
                # Semantic
                ("[itemprop=price]",                    lambda: (lambda e: e.get_attribute("content") or e.inner_text() if e else None)(page.query_selector("[itemprop='price']"))),
                # Amazon price selectors
                ("#corePrice_feature_div .a-offscreen", lambda: (lambda e: e.inner_text() if e else None)(page.query_selector("#corePrice_feature_div .a-offscreen"))),
                (".apexPriceToPay .a-offscreen",        lambda: (lambda e: e.inner_text() if e else None)(page.query_selector(".apexPriceToPay .a-offscreen"))),
                ("span.a-price-whole",                  lambda: (lambda e: e.inner_text() if e else None)(page.query_selector("span.a-price-whole"))),
                # Amazon field selectors
                ("#productTitle",                       lambda: (lambda e: e.inner_text().strip()[:60] if e else None)(page.query_selector("#productTitle"))),
                ("#bylineInfo",                         lambda: (lambda e: e.inner_text().strip()[:60] if e else None)(page.query_selector("#bylineInfo"))),
                ("#landingImage @src",                  lambda: (lambda e: (e.get_attribute("src") or "")[:60] if e else None)(page.query_selector("#landingImage"))),
                ("#availability span",                  lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("#availability span"))),
                ("span[data-hook=rating-out-of-text]",  lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("span[data-hook='rating-out-of-text']"))),
                ("#acrCustomerReviewText",              lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("#acrCustomerReviewText"))),
                ("#sellerProfileTriggerId",             lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("#sellerProfileTriggerId"))),
                # Flipkart price selectors
                ("div[class*='Nx9bqj']",                lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("div[class*='Nx9bqj']"))),
                ("div[class*='CxhGGd']",                lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("div[class*='CxhGGd']"))),
                ("div._30jeq3._16Jk6d",                 lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("div._30jeq3._16Jk6d"))),
                ("div._30jeq3",                         lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("div._30jeq3"))),
                ("[data-testid='product-price']",       lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("[data-testid='product-price']"))),
                # Flipkart field selectors
                ("span.B_NuCI",                         lambda: (lambda e: e.inner_text().strip()[:60] if e else None)(page.query_selector("span.B_NuCI"))),
                ("h1.yhB1nd",                           lambda: (lambda e: e.inner_text().strip()[:60] if e else None)(page.query_selector("h1.yhB1nd"))),
                ("span._2gy4qV",                        lambda: (lambda e: e.inner_text().strip()[:40] if e else None)(page.query_selector("span._2gy4qV"))),
                ("img._396cs4 @src",                    lambda: (lambda e: (e.get_attribute("src") or "")[:60] if e else None)(page.query_selector("img._396cs4"))),
                ("div#sellerName span",                  lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("div#sellerName span"))),
            ]
            for label, fn in probes:
                try:
                    val = fn()
                    status = f"✅  {val!r}" if val else "❌  (not found)"
                except Exception as exc:
                    status = f"💥  {exc}"
                print(f"  {label:<45} {status}")

            context.close()
            browser.close()
            return

        response = scraper.scrape(
            page=page,
            url=url,
            config=config,
            job_id="test-run",
            attempt_number=1,
        )

        # Post-scrape probe — runs on the same page after scrape() returns.
        # Helps diagnose fields that came back null despite selectors existing.
        if verbose and response.success:
            print("\n── Post-scrape selector probe ───────────────────────────")
            post_probes = [
                ("#productTitle",              lambda: (lambda e: e.inner_text().strip()[:70] if e else None)(page.query_selector("#productTitle"))),
                ("#bylineInfo",                lambda: (lambda e: e.inner_text().strip()[:60] if e else None)(page.query_selector("#bylineInfo"))),
                ("#landingImage @src",         lambda: (lambda e: (e.get_attribute("src") or "")[:60] if e else None)(page.query_selector("#landingImage"))),
                ("#availability span",         lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("#availability span"))),
                ("rating [data-hook]",         lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("span[data-hook='rating-out-of-text']"))),
                ("#acrCustomerReviewText",     lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("#acrCustomerReviewText"))),
                ("#sellerProfileTriggerId",    lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("#sellerProfileTriggerId"))),
                ("#corePrice_feature_div .a-offscreen", lambda: (lambda e: e.inner_text().strip() if e else None)(page.query_selector("#corePrice_feature_div .a-offscreen"))),
                ("meta og:title",               lambda: (lambda e: (e.get_attribute("content") or "")[:80] if e else None)(page.query_selector("meta[property='og:title']"))),
                ("page.url",                   lambda: page.url),
            ]
            for label, fn in post_probes:
                try:
                    val = fn()
                    status = f"✅  {val!r}" if val else "❌  (not found)"
                except Exception as exc:
                    status = f"💥  {exc}"
                print(f"  {label:<45} {status}")

        context.close()
        browser.close()

    # ── Print results ─────────────────────────────────────────────────────────
    if response.success:
        print(f"✅  SCRAPE SUCCEEDED")
        print(f"\n── Product ──────────────────────────────────────")
        print(f"  Price       : ₹{response.current_price}")
        print(f"  Name        : {response.name or '(not found)'}")
        print(f"  Brand       : {response.brand or '(not found)'}")
        print(f"  Product ID  : {response.marketplace_product_id or '(not found)'}")
        print(f"  Availability: {'In Stock' if response.availability else 'Out of Stock'}")
        print(f"  Rating      : {response.rating or '(not found)'}")
        print(f"  Reviews     : {response.review_count or '(not found)'}")
        print(f"  Seller      : {response.seller or '(not found)'}")
        print(f"  Image URL   : {(response.image_url or '')[:80] or '(not found)'}")

        print(f"\n── Diagnostics ──────────────────────────────────")
        print(f"  Extraction method : {response.extraction_method}")
        print(f"  Layers attempted  : {response.layers_attempted}")
        print(f"  Layers failed     : {response.layers_failed}")
        print(f"  Navigation        : {response.navigation_ms}ms")
        print(f"  Extraction        : {response.extraction_ms}ms")
        print(f"  Total             : {response.total_duration_ms}ms")
    else:
        print(f"❌  SCRAPE FAILED")
        print(f"\n── Error ────────────────────────────────────────")
        print(f"  Error type    : {response.error_type}")
        print(f"  Error message : {response.error_message}")
        print(f"\n── Diagnostics ──────────────────────────────────")
        print(f"  Layers attempted : {response.layers_attempted}")
        print(f"  Layers failed    : {response.layers_failed}")
        print(f"  Navigation       : {response.navigation_ms}ms")
        print(f"  Total            : {response.total_duration_ms}ms")

    if verbose:
        print(f"\n── Full Response (JSON) ─────────────────────────")
        d = asdict(response)
        d["current_price"] = str(d["current_price"]) if d["current_price"] else None
        d["rating"] = str(d["rating"]) if d["rating"] else None
        print(json.dumps(d, indent=2, default=str))

    print(f"\n{'='*60}\n")


def inspect_html(path: str) -> None:
    """
    Read a locally saved HTML dump and find price/field elements
    using BeautifulSoup. Run after --dump-html to find current selectors.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("pip install beautifulsoup4 lxml")
        sys.exit(1)

    import json, re
    html = open(path, encoding="utf-8").read()
    soup = BeautifulSoup(html, "lxml")

    print(f"\n{'='*60}")
    print(f"  Inspecting: {path}  ({len(html):,} bytes)")
    print(f"{'='*60}")

    # ── JSON-LD ───────────────────────────────────────────────────────────────
    print("\n── JSON-LD blocks ───────────────────────────────────────────")
    for i, tag in enumerate(soup.find_all("script", type="application/ld+json")):
        try:
            data = json.loads(tag.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                t = item.get("@type", "?")
                offers = item.get("offers", {})
                if isinstance(offers, list):
                    prices = [o.get("price") for o in offers]
                    price = prices[0] if prices else None
                else:
                    price = offers.get("price")
                name = item.get("name", "")[:60]
                print(f"  [{i}] @type={t}  price={price}  name={name!r}")
        except Exception as e:
            print(f"  [{i}] parse error: {e}")

    # ── Find price candidates ─────────────────────────────────────────────────
    print("\n── Price candidates (₹ or digits with comma pattern) ────────")
    price_re = re.compile(r"₹[ ]?[\d,]+|[\d]{1,3}(?:,[\d]{3})+")
    seen = set()
    candidates = []
    for tag in soup.find_all(string=price_re):
        parent = tag.parent
        if parent.name in ("script", "style", "meta"):
            continue
        text = tag.strip()
        if text in seen or len(text) > 20:
            continue
        seen.add(text)
        # Build a short CSS selector for this element
        classes = " ".join(parent.get("class", []))
        pid = parent.get("id", "")
        sel = parent.name
        if pid:
            sel += f"#{pid}"
        elif classes:
            # Show first 2 classes only
            cls_short = ".".join(classes.split()[:2])
            sel += f".{cls_short}"
        candidates.append((text, sel, parent.get("class", [])))

    for text, sel, classes in candidates[:20]:
        print(f"  {text:<20}  <{sel}>   classes={classes[:3]}")

    # ── Find title candidates ─────────────────────────────────────────────────
    print("\n── Title candidates (h1, h2 with >10 chars) ────────────────")
    for tag in soup.find_all(["h1", "h2"]):
        text = tag.get_text(strip=True)[:80]
        if len(text) > 10:
            classes = ".".join(tag.get("class", []))
            print(f"  <{tag.name}.{classes}>  {text!r}")

    # ── Find image candidates ─────────────────────────────────────────────────
    print("\n── Image candidates (large img src, not icon) ───────────────")
    for tag in soup.find_all("img"):
        src = tag.get("src", "") or tag.get("data-src", "")
        if not src or "icon" in src or "logo" in src:
            continue
        if src.startswith("data:"):
            continue
        classes = ".".join(tag.get("class", []))
        print(f"  <img.{classes}>  {src[:70]}")
        if len([t for t in soup.find_all("img") if t.get("src", "")]) > 10:
            break  # stop after first meaningful batch

    # ── Find seller candidates ────────────────────────────────────────────────
    print("\n── Seller candidates (text near 'Sold by' or 'Seller') ─────")
    for tag in soup.find_all(string=re.compile(r"Sold by|Seller|seller", re.I)):
        parent = tag.parent
        # grab sibling or parent text
        context = parent.get_text(strip=True)[:100]
        classes = ".".join(parent.get("class", []))
        print(f"  <{parent.name}.{classes}>  {context!r}")

    # ── Find rating candidates ────────────────────────────────────────────────
    print("\n── Rating candidates (x.x out of 5) ────────────────────────")
    for tag in soup.find_all(string=re.compile(r"\d\.\d")):
        text = tag.strip()
        if "out of" in text.lower() or (len(text) < 5 and "." in text):
            parent = tag.parent
            classes = ".".join(parent.get("class", []))
            print(f"  <{parent.name}.{classes}>  {text!r}")

    print(f"\n{'='*60}\n")


def test_curl_cffi(url: str) -> None:
    """
    Test fetching a URL using curl_cffi which impersonates real browser
    TLS fingerprints. Useful for portals that block Playwright headless
    at the TLS level (e.g. Myntra).

    Install: pip install curl_cffi
    """
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        print("\ncurl_cffi not installed. Run:")
        print("  pip install curl_cffi --break-system-packages")
        return

    import re, json

    print(f"\n{'='*60}")
    print(f"  curl_cffi TLS impersonation test")
    print(f"  URL: {url}")
    print(f"{'='*60}\n")

    for impersonate in ["chrome124", "chrome110", "firefox117"]:
        try:
            print(f"  Trying impersonate={impersonate!r} ...", end=" ", flush=True)
            resp = cffi_requests.get(
                url,
                impersonate=impersonate,
                headers={
                    "Accept-Language": "en-IN,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                timeout=15,
            )
            print(f"HTTP {resp.status_code}  size={len(resp.text):,} bytes")
            if resp.status_code == 200 and len(resp.text) > 50000:
                # Check for JSON-LD
                ld_matches = re.findall(
                    r'<script[^>]+type=[^>]*application/ld[^>]*>(.*?)</script>',
                    resp.text, re.DOTALL | re.IGNORECASE
                )
                print(f"  JSON-LD blocks found: {len(ld_matches)}")
                for i, block in enumerate(ld_matches[:3]):
                    try:
                        data = json.loads(block)
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            if item.get("@type") == "Product":
                                offers = item.get("offers", {})
                                if isinstance(offers, list): offers = offers[0]
                                price = offers.get("price") if isinstance(offers, dict) else None
                                print(f"  ✅ Product found — name={str(item.get('name',''))[:60]!r} price={price}")
                    except Exception:
                        pass
                print(f"  ✅ SUCCESS with {impersonate}")
                break
        except Exception as exc:
            print(f"FAILED — {exc}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scraper_v2.run_test <url> [--verbose]")
        sys.exit(1)

    target_url = sys.argv[1]
    is_verbose = "--verbose" in sys.argv or "-v" in sys.argv
    is_headless = "--no-headless" not in sys.argv  # headless=True by default
    is_dump = "--dump-html" in sys.argv
    is_inspect = "--inspect-html" in sys.argv
    is_firefox = "--firefox" in sys.argv
    is_curl = "--curl-cffi" in sys.argv
    if is_inspect:
        dump_path = sys.argv[sys.argv.index("--inspect-html") + 1] if "--inspect-html" in sys.argv and sys.argv.index("--inspect-html") + 1 < len(sys.argv) and not sys.argv[sys.argv.index("--inspect-html") + 1].startswith("--") else "/tmp/amazon_dump.html"
        inspect_html(dump_path)
        sys.exit(0)
    if is_curl:
        test_curl_cffi(target_url)
        sys.exit(0)
    run(target_url, verbose=is_verbose, headless=is_headless, dump_html=is_dump, use_firefox=is_firefox)
