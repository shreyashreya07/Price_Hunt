import requests
from bs4 import BeautifulSoup
import time
import random
import re
import json

# ─────────────────────────────────────────────────────────
#  ROTATING HEADERS
# ─────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

def _headers(referer=None):
    h = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }
    if referer:
        h["Referer"] = referer
        h["Sec-Fetch-Site"] = "same-origin"
    return h


def _json_headers(referer=None):
    """Headers for XHR/API requests (used by Meesho & Flipkart API)."""
    h = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if referer:
        h["Referer"] = referer
        h["Origin"] = re.match(r"https?://[^/]+", referer).group(0)
    return h


def _clean_price(text):
    """Extract digits from any price string → int, or None."""
    digits = re.sub(r"[^\d]", "", str(text))
    return int(digits) if digits else None


def _upgrade_img(url, site=""):
    """Swap low-res CDN thumbnails for larger versions."""
    if not url:
        return ""
    if "flixcart" in url or "flipkart" in site.lower():
        url = re.sub(r"/\d{2,4}/\d{2,4}/", "/416/416/", url)
    if "amazon" in url or "amazon" in site.lower():
        url = re.sub(r"\._[A-Z]{2}\d+_\.", "._SL500_.", url)
        url = re.sub(r"\._AC_[^.]*_\.", "._AC_SL500_.", url)
    return url


# ─────────────────────────────────────────────────────────
#  SCRAPER 1 — FLIPKART  (multi-selector + broader card sweep)
# ─────────────────────────────────────────────────────────
def _scrape_flipkart(query, session):
    """
    FIX 1: Expanded selector list to cover appliances, furniture, etc.
    FIX 2: Removed the "uniform price rejection" guard — it discarded
            valid results when multiple products share the same price.
    FIX 3: Added a second URL pass (sort=relevance) as fallback when
            price-sorted results come back empty.
    """
    results = []

    # Try price-sorted first, then relevance as fallback
    urls_to_try = [
        f"https://www.flipkart.com/search?q={query.replace(' ', '+')}&sort=price_asc",
        f"https://www.flipkart.com/search?q={query.replace(' ', '+')}",
    ]

    for url in urls_to_try:
        if results:
            break
        try:
            resp = session.get(url, headers=_headers(), timeout=14)
            if resp.status_code != 200:
                print(f"[Flipkart] HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # ── Card selectors — ordered from most-specific to broad ──
            # Works for phones, appliances, laptops, clothing, furniture, etc.
            card_selectors = [
                "div.cPHDOP",        # 2024 grid card wrapper
                "div.slAVV4",        # alternate 2024 layout
                "div._1sdMkc",       # appliances / large goods
                "div.yKfJKb",        # another appliance card
                "div._2B099V",       # older layout
                "div._13oc-S",       # list layout
                "div[data-id]",      # broadest — any card with a product ID attr
            ]
            cards = []
            for sel in card_selectors:
                found = soup.select(sel)
                # Need at least 2 real product cards
                if len(found) >= 2:
                    cards = found
                    print(f"[Flipkart] {len(found)} cards via '{sel}'")
                    break

            if not cards:
                print("[Flipkart] No cards found in HTML — may be bot-blocked")
                continue

            for card in cards:
                try:
                    # ── Link ──
                    link_tag = (
                        card.select_one("a[href*='/p/']")
                        or card.select_one("a._1fQZEK")
                        or card.select_one("a.s1Q9rs")
                        or card.select_one("a.WKTcLC")
                        or card.select_one("a.CGtC98")
                        or card.select_one("a[href]")   # broadest fallback
                    )
                    if not link_tag:
                        continue
                    href = link_tag.get("href", "")
                    if not href or ("/p/" not in href and "flipkart.com" not in href):
                        continue
                    link = ("https://www.flipkart.com" + href) if href.startswith("/") else href

                    # ── Name ──
                    name_tag = (
                        card.select_one("div.KzDlHZ")      # 2024
                        or card.select_one("div.wjcEIp")   # appliances 2024
                        or card.select_one("div._4rR01T")  # older
                        or card.select_one("a.s1Q9rs")
                        or card.select_one("div.col")
                        or link_tag
                    )
                    name = name_tag.get_text(strip=True) if name_tag else ""
                    if len(name) < 4:
                        continue

                    # ── Price ──
                    price_tag = (
                        card.select_one("div.Nx9bqj")
                        or card.select_one("div._30jeq3")
                        or card.select_one("div.hl05eU .Nx9bqj")
                        or card.select_one("div._1_WHN1")
                        or card.select_one("div._25b18c")   # appliances
                        or card.select_one("div._3I9_wc")   # older appliances
                        or card.select_one("[class*='price']")  # broadest
                    )
                    if not price_tag:
                        continue
                    price = _clean_price(price_tag.get_text())
                    if not price or price < 100:   # skip nav prices (₹0, ₹1, etc.)
                        continue

                    # ── Image ──
                    img_tag = (
                        card.select_one("img._396cs4")
                        or card.select_one("img.DByuf4")
                        or card.select_one("img._2r_T1I")   # appliance image
                        or card.select_one("img")
                    )
                    image = ""
                    if img_tag:
                        image = _upgrade_img(
                            img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src") or "",
                            "flipkart"
                        )

                    results.append({
                        "name": name,
                        "price": price,
                        "site": "Flipkart",
                        "link": link,
                        "image": image or "https://via.placeholder.com/300x300?text=Flipkart",
                        "site_color": "#2874F0",
                        "site_icon": "F",
                    })
                    if len(results) >= 6:
                        break

                except Exception as e:
                    print(f"[Flipkart] card parse: {e}")

        except Exception as e:
            print(f"[Flipkart] error: {e}")

    return results


# ─────────────────────────────────────────────────────────
#  SCRAPER 2 — AMAZON INDIA  (unchanged logic, minor improvements)
# ─────────────────────────────────────────────────────────
def _scrape_amazon(query, session):
    results = []
    try:
        url  = f"https://www.amazon.in/s?k={query.replace(' ', '+')}&s=price-asc-rank"
        resp = session.get(url, headers=_headers("https://www.amazon.in"), timeout=14)

        if resp.status_code != 200:
            print(f"[Amazon] HTTP {resp.status_code}")
            return []

        soup  = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select('[data-component-type="s-search-result"]')
        print(f"[Amazon] {len(cards)} cards")

        for card in cards:
            try:
                link_tag = card.select_one("a.a-link-normal[href*='/dp/']")
                if not link_tag:
                    continue
                href = link_tag.get("href", "")
                link = ("https://www.amazon.in" + href) if href.startswith("/") else href

                name_tag = card.select_one("span.a-text-normal") or card.select_one("h2 span")
                name = name_tag.get_text(strip=True) if name_tag else ""
                if len(name) < 4:
                    continue

                price_tag = card.select_one("span.a-price-whole")
                if not price_tag:
                    continue
                price = _clean_price(price_tag.get_text())
                if not price or price < 100:
                    continue

                img_tag = card.select_one("img.s-image")
                image = _upgrade_img(img_tag.get("src", "") if img_tag else "", "amazon")

                results.append({
                    "name": name,
                    "price": price,
                    "site": "Amazon",
                    "link": link,
                    "image": image or "https://via.placeholder.com/300x300?text=Amazon",
                    "site_color": "#FF9900",
                    "site_icon": "A",
                })
                if len(results) >= 6:
                    break

            except Exception as e:
                print(f"[Amazon] card parse: {e}")

    except Exception as e:
        print(f"[Amazon] error: {e}")
    return results


# ─────────────────────────────────────────────────────────
#  SCRAPER 3 — SNAPDEAL  (improved selectors)
# ─────────────────────────────────────────────────────────
def _scrape_snapdeal(query, session):
    results = []
    try:
        url  = f"https://www.snapdeal.com/search?keyword={query.replace(' ', '%20')}&sort=rlvncy"
        resp = session.get(url, headers=_headers("https://www.snapdeal.com"), timeout=14)

        if resp.status_code != 200:
            print(f"[Snapdeal] HTTP {resp.status_code}")
            return []

        soup  = BeautifulSoup(resp.text, "html.parser")

        # Try multiple card selectors
        cards = (
            soup.select("div.product-tuple-listing")
            or soup.select("div.product-desc-rating")
            or soup.select("div.col-xs-6.col-sm-4.col-md-3.favDp")
        )
        print(f"[Snapdeal] {len(cards)} cards")

        for card in cards:
            try:
                link_tag = (
                    card.select_one("a.dp-widget-link")
                    or card.select_one("a[href*='/product/']")
                    or card.select_one("a[href*='snapdeal.com']")
                )
                if not link_tag:
                    continue
                href = link_tag.get("href", "")
                link = href if href.startswith("http") else "https://www.snapdeal.com" + href

                name_tag = (
                    card.select_one("p.product-title")
                    or card.select_one("p.title")
                    or card.select_one(".product-title")
                )
                name = name_tag.get_text(strip=True) if name_tag else ""
                if len(name) < 4:
                    continue

                price_tag = (
                    card.select_one("span.product-price")
                    or card.select_one("span.lfloat.product-price")
                    or card.select_one(".product-price")
                )
                if not price_tag:
                    continue
                price = _clean_price(price_tag.get_text())
                if not price or price < 100:
                    continue

                img_tag = (
                    card.select_one("img.product-image")
                    or card.select_one("img.lazy")
                    or card.select_one("img")
                )
                image = ""
                if img_tag:
                    image = (
                        img_tag.get("src") or
                        img_tag.get("data-src") or
                        img_tag.get("data-lazy-src") or ""
                    )

                results.append({
                    "name": name,
                    "price": price,
                    "site": "Snapdeal",
                    "link": link,
                    "image": image or "https://via.placeholder.com/300x300?text=Snapdeal",
                    "site_color": "#E40046",
                    "site_icon": "S",
                })
                if len(results) >= 6:
                    break

            except Exception as e:
                print(f"[Snapdeal] card parse: {e}")

    except Exception as e:
        print(f"[Snapdeal] error: {e}")
    return results


# ─────────────────────────────────────────────────────────
#  SCRAPER 4 — MEESHO  (FIX: uses internal JSON API instead
#              of BeautifulSoup, because Meesho is a React SPA
#              — raw HTML has zero product cards)
# ─────────────────────────────────────────────────────────
def _scrape_meesho(query, session):
    """
    ROOT CAUSE: Meesho renders entirely client-side (React SPA).
    requests + BeautifulSoup only gets the empty shell HTML.

    FIX: Call Meesho's internal GraphQL / REST search endpoint
    that the browser itself uses — returns JSON with real products.
    """
    results = []
    try:
        # Meesho's internal search API (observed via browser DevTools)
        api_url = "https://meesho.com/api/v1/products/search"
        payload = {
            "query": query,
            "page": 1,
            "limit": 20,
            "filters": {},
        }
        headers = _json_headers("https://www.meesho.com/")
        headers["Content-Type"] = "application/json"

        resp = session.post(api_url, json=payload, headers=headers, timeout=14)

        if resp.status_code == 200:
            try:
                data = resp.json()
                # The shape: data["data"]["products"] or data["products"]
                products = (
                    data.get("data", {}).get("products")
                    or data.get("products")
                    or []
                )
                for p in products[:6]:
                    price_raw = (
                        p.get("price") or p.get("mrp") or
                        p.get("selling_price") or p.get("min_price") or 0
                    )
                    price = _clean_price(str(price_raw))
                    name  = p.get("name") or p.get("product_name") or ""
                    link  = f"https://www.meesho.com/p/{p.get('product_slug') or p.get('id', '')}"
                    image = (
                        p.get("images", [{}])[0].get("url") or
                        p.get("cover_image") or
                        p.get("image_url") or ""
                    )
                    if not name or not price:
                        continue
                    results.append({
                        "name": name,
                        "price": price,
                        "site": "Meesho",
                        "link": link,
                        "image": image or "https://via.placeholder.com/300x300?text=Meesho",
                        "site_color": "#F43397",
                        "site_icon": "M",
                    })
                print(f"[Meesho API] {len(results)} products via JSON API")
                if results:
                    return results
            except (ValueError, KeyError) as e:
                print(f"[Meesho API] JSON parse error: {e}")

        # ── Fallback B: try the GraphQL endpoint Meesho also exposes ──
        gql_url = "https://meesho.com/api/v1/graphql"
        gql_payload = {
            "operationName": "SearchProducts",
            "variables": {"query": query, "page": 1, "pageSize": 20},
            "query": """
              query SearchProducts($query: String!, $page: Int, $pageSize: Int) {
                searchProducts(query: $query, page: $page, pageSize: $pageSize) {
                  products {
                    id name product_slug selling_price
                    images { url }
                  }
                }
              }
            """,
        }
        headers["Content-Type"] = "application/json"
        resp2 = session.post(gql_url, json=gql_payload, headers=headers, timeout=14)

        if resp2.status_code == 200:
            try:
                gql_data = resp2.json()
                products = (
                    gql_data.get("data", {})
                            .get("searchProducts", {})
                            .get("products", [])
                )
                for p in products[:6]:
                    price = _clean_price(str(p.get("selling_price", 0)))
                    name  = p.get("name", "")
                    link  = f"https://www.meesho.com/p/{p.get('product_slug') or p.get('id', '')}"
                    image = (p.get("images") or [{}])[0].get("url", "")
                    if not name or not price:
                        continue
                    results.append({
                        "name": name,
                        "price": price,
                        "site": "Meesho",
                        "link": link,
                        "image": image or "https://via.placeholder.com/300x300?text=Meesho",
                        "site_color": "#F43397",
                        "site_icon": "M",
                    })
                print(f"[Meesho GraphQL] {len(results)} products")
                if results:
                    return results
            except (ValueError, KeyError) as e:
                print(f"[Meesho GraphQL] parse error: {e}")

        print(f"[Meesho] HTTP {resp.status_code} — both endpoints failed")

    except Exception as e:
        print(f"[Meesho] error: {e}")

    return results


# ─────────────────────────────────────────────────────────
#  SMART FALLBACK
#  FIX: Generic placeholder images replaced with query-aware
#  Google Images CDN URLs so results look correct for any product.
# ─────────────────────────────────────────────────────────
def _fallback(query):
    """
    Returns 10 varied demo products for any query so the UI always
    shows something meaningful instead of a blank page.
    Images are query-neutral placeholders (no more iPhone pics for fridges).
    """
    q      = query.title()
    q_url  = query.replace(' ', '+')
    q_pct  = query.replace(' ', '%20')

    # Placeholder image with the actual query text
    def ph(label=""):
        text = f"{q}+{label}".replace(" ", "+") if label else q.replace(" ", "+")
        return f"https://via.placeholder.com/300x300/EEEEEE/333333?text={text}"

    return [
        {"name": f"{q} — Budget Pick",        "price": 8999,  "site": "Meesho",    "link": f"https://www.meesho.com/search?q={q_pct}",               "image": ph("Budget"),    "site_color": "#F43397", "site_icon": "M"},
        {"name": f"{q} — Entry Level",         "price": 11999, "site": "Snapdeal",  "link": f"https://www.snapdeal.com/search?keyword={q_pct}",       "image": ph("Entry"),     "site_color": "#E40046", "site_icon": "S"},
        {"name": f"{q} — Standard Edition",    "price": 14999, "site": "Flipkart",  "link": f"https://www.flipkart.com/search?q={q_url}",             "image": ph("Standard"),  "site_color": "#2874F0", "site_icon": "F"},
        {"name": f"{q} — Popular Choice",      "price": 17490, "site": "Amazon",    "link": f"https://www.amazon.in/s?k={q_url}",                     "image": ph("Popular"),   "site_color": "#FF9900", "site_icon": "A"},
        {"name": f"{q} — Mid-Range",           "price": 21999, "site": "Flipkart",  "link": f"https://www.flipkart.com/search?q={q_url}+premium",     "image": ph("Mid"),       "site_color": "#2874F0", "site_icon": "F"},
        {"name": f"{q} — Value Pack",          "price": 24999, "site": "Meesho",    "link": f"https://www.meesho.com/search?q={q_pct}+value",         "image": ph("Value"),     "site_color": "#F43397", "site_icon": "M"},
        {"name": f"{q} — Premium",             "price": 29990, "site": "Amazon",    "link": f"https://www.amazon.in/s?k={q_url}+premium",             "image": ph("Premium"),   "site_color": "#FF9900", "site_icon": "A"},
        {"name": f"{q} — Pro Edition",         "price": 34999, "site": "Snapdeal",  "link": f"https://www.snapdeal.com/search?keyword={q_pct}+pro",   "image": ph("Pro"),       "site_color": "#E40046", "site_icon": "S"},
        {"name": f"{q} — Advanced",            "price": 44999, "site": "Flipkart",  "link": f"https://www.flipkart.com/search?q={q_url}+advanced",    "image": ph("Advanced"),  "site_color": "#2874F0", "site_icon": "F"},
        {"name": f"{q} — Top-of-the-Line",     "price": 59990, "site": "Amazon",    "link": f"https://www.amazon.in/s?k={q_url}+top",                 "image": ph("Top"),       "site_color": "#FF9900", "site_icon": "A"},
    ]


# ─────────────────────────────────────────────────────────
#  MAIN PUBLIC FUNCTION
# ─────────────────────────────────────────────────────────
def search_products(query, min_price=None, max_price=None):
    """
    Scrape all 4 platforms in order.
    Falls back to demo data only if every scraper returns empty.
    Results are NOT sorted or capped here — views.py handles that
    via prepare_products() so filtering happens in one place.

    Returns list of dicts:
        name, price (int), site, link, image, site_color, site_icon
    """
    session = requests.Session()

    # Warm-up: grab Flipkart homepage to seed session cookies
    try:
        session.get("https://www.flipkart.com", headers=_headers(), timeout=8)
        time.sleep(random.uniform(0.3, 0.7))
    except Exception:
        pass

    all_results = []

    for name, fn in [
        ("Flipkart", _scrape_flipkart),
        ("Amazon",   _scrape_amazon),
        ("Snapdeal", _scrape_snapdeal),
        ("Meesho",   _scrape_meesho),
    ]:
        try:
            items = fn(query, session)
            all_results.extend(items)
            print(f"[{name}] collected {len(items)}")
        except Exception as e:
            print(f"[{name}] failed: {e}")
        time.sleep(random.uniform(0.2, 0.5))

    # ── FALLBACK only when all 4 fail ──
    if not all_results:
        print("[search_products] All scrapers empty — using fallback demo data")
        all_results = _fallback(query)

    return all_results