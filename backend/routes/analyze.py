import asyncio
import re
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from services.review_aggregator import ReviewAggregator
from services.claude_analyzer import ClaudeAnalyzer
from services.price_estimator import PriceEstimator

router = APIRouter()

# Lazy singletons: each service is instantiated once on first request and reused for all subsequent calls
_price_estimator = None
_review_aggregator = None
_claude_analyzer = None

def get_price_estimator():
    global _price_estimator
    if _price_estimator is None:
        _price_estimator = PriceEstimator()
    return _price_estimator

def get_review_aggregator():
    global _review_aggregator
    if _review_aggregator is None:
        _review_aggregator = ReviewAggregator()
    return _review_aggregator

def get_claude_analyzer():
    global _claude_analyzer
    if _claude_analyzer is None:
        _claude_analyzer = ClaudeAnalyzer()
    return _claude_analyzer


class AnalyzeRequest(BaseModel):
    title: str
    seller: str
    price: float
    source: str
    url: Optional[str] = ""
    google_place_id: Optional[str] = None


# In-memory seller → domain cache; populated during DDG lookups and lives for the process lifetime
_seller_domain_cache: dict = {}

def _seller_domain(seller: str) -> Optional[str]:
    # Maps a seller name to its domain for DuckDuckGo site: searches.
    # Checks the static KNOWN dict first (instant), then falls back to joined-word heuristic.
    KNOWN = {
        # big-box / electronics
        "gamestop": "gamestop.com",
        "best buy": "bestbuy.com",
        "amazon": "amazon.com",
        "walmart": "walmart.com",
        "target": "target.com",
        "costco": "costco.com",
        "sam's club": "samsclub.com",
        "bj's": "bjs.com",
        "newegg": "newegg.com",
        "micro center": "microcenter.com",
        "b&h": "bhphotovideo.com",
        "b&h photo": "bhphotovideo.com",
        "adorama": "adorama.com",
        # marketplaces
        "ebay": "ebay.com",
        "etsy": "etsy.com",
        "rakuten": "rakuten.com",
        "overstock": "overstock.com",
        "wish": "wish.com",
        "alibaba": "alibaba.com",
        # fashion / apparel
        "nike": "nike.com",
        "adidas": "adidas.com",
        "under armour": "underarmour.com",
        "foot locker": "footlocker.com",
        "footlocker": "footlocker.com",
        "finish line": "finishline.com",
        "dick's sporting": "dickssportinggoods.com",
        "dicks sporting": "dickssportinggoods.com",
        "academy sports": "academy.com",
        "nordstrom": "nordstrom.com",
        "macy's": "macys.com",
        "macys": "macys.com",
        "bloomingdale": "bloomingdales.com",
        "gap": "gap.com",
        "old navy": "oldnavy.com",
        "banana republic": "bananarepublic.com",
        "h&m": "hm.com",
        "zara": "zara.com",
        "uniqlo": "uniqlo.com",
        "levi's": "levi.com",
        "levis": "levi.com",
        "patagonia": "patagonia.com",
        "columbia": "columbia.com",
        "the north face": "thenorthface.com",
        "north face": "thenorthface.com",
        # home / furniture
        "wayfair": "wayfair.com",
        "crate and barrel": "crateandbarrel.com",
        "west elm": "westelm.com",
        "pottery barn": "potterybarn.com",
        "ikea": "ikea.com",
        "home depot": "homedepot.com",
        "homedepot": "homedepot.com",
        "lowe's": "lowes.com",
        "lowes": "lowes.com",
        "menards": "menards.com",
        "bed bath": "bedbathandbeyond.com",
        "williams sonoma": "williams-sonoma.com",
        # tech / computers
        "apple": "apple.com",
        "samsung": "samsung.com",
        "sony": "sony.com",
        "microsoft": "microsoft.com",
        "dell": "dell.com",
        "hp": "hp.com",
        "lenovo": "lenovo.com",
        "asus": "asus.com",
        "acer": "acer.com",
        "lg": "lg.com",
        "logitech": "logitech.com",
        "razer": "razer.com",
        "corsair": "corsair.com",
        # pets
        "chewy": "chewy.com",
        "petco": "petco.com",
        "petsmart": "petsmart.com",
        "pet supplies plus": "petsuppliesplus.com",
        # beauty / health
        "ulta": "ulta.com",
        "sephora": "sephora.com",
        "cvs": "cvs.com",
        "walgreens": "walgreens.com",
        "rite aid": "riteaid.com",
        "gnc": "gnc.com",
        "vitamin shoppe": "vitaminshoppe.com",
        # specialty
        "guitar center": "guitarcenter.com",
        "guitar world": "guitarworld.com",
        "sweetwater": "sweetwater.com",
        "rei": "rei.com",
        "cabela's": "cabelas.com",
        "bass pro": "basspro.com",
        "autozone": "autozone.com",
        "advance auto": "advanceautoparts.com",
        "o'reilly": "oreillyauto.com",
        "pep boys": "pepboys.com",
        "staples": "staples.com",
        "office depot": "officedepot.com",
        "officemax": "officedepot.com",
        "toys r us": "toysrus.com",
        "build-a-bear": "buildabear.com",
        # nicotine / tobacco
        "nicokick": "nicokick.com",
        "northerner": "northerner.com",
        "whitesnuff": "whitesnuff.com",
        "us nicotine": "usnicotinepouches.com",
    }
    lower = seller.lower().strip()
    for key, domain in KNOWN.items():
        if key in lower:
            return domain

    # Check the runtime cache populated by _resolve_seller_domain() during this session
    if lower in _seller_domain_cache:
        return _seller_domain_cache[lower]

    # Derive a best-guess domain by joining up to 3 words: "Guitar Center" → "guitarcenter.com"
    # More accurate than using the first word alone for multi-word brand names
    words = re.findall(r"[a-z0-9]+", lower)
    if not words:
        return None

    # Join up to 3 words to form the domain (e.g. "Home Depot" → "homedepot.com")
    joined = "".join(words[:3])  # max 3 words to avoid noise
    return f"{joined}.com"


async def _resolve_seller_domain(seller: str) -> Optional[str]:
    """
    For sellers NOT in the KNOWN dict, use DDG to find their actual homepage,
    then extract the domain. Result is cached per process lifetime.
    """
    lower = seller.lower().strip()
    if lower in _seller_domain_cache:
        return _seller_domain_cache[lower]

    # Build a heuristic guess before hitting DDG; used as fallback if DDG returns no usable result
    words = re.findall(r"[a-z0-9]+", lower)
    joined = "".join(words[:3])
    guessed = f"{joined}.com" if joined else None

    try:
        def _ddg_homepage():
            from ddgs import DDGS
            with DDGS(verify=False) as ddgs:
                return list(ddgs.text(f"{seller} official website", max_results=3))

        results = await asyncio.wait_for(
            asyncio.to_thread(_ddg_homepage),
            timeout=5.0,
        )

        from urllib.parse import urlparse
        for r in results:
            href = r.get("href", "")
            if not href:
                continue
            parsed = urlparse(href)
            netloc = parsed.netloc.replace("www.", "")
            # Accept if the domain contains any word from the seller name
            if any(w in netloc for w in words[:2] if len(w) > 2):
                _seller_domain_cache[lower] = netloc
                print(f"[DomainResolve] '{seller}' → {netloc}")
                return netloc

    except Exception as e:
        print(f"[DomainResolve] Failed for '{seller}': {e}")

    # Fall back to guessed domain
    if guessed:
        _seller_domain_cache[lower] = guessed
    return guessed


def _score_product_url(href: str) -> int:
    """
    Scores a URL — higher score = more likely to be a specific product page.
    Returns -1 if the URL should be rejected entirely (homepage/search/category).
    """
    from urllib.parse import urlparse
    parsed = urlparse(href)
    path = parsed.path.strip("/")

    # Reject homepages (no path) and very shallow paths that are unlikely to be product pages
    if not path or len(path) < 8:
        return -1

    # Reject obvious search result pages, browse pages, and category landing pages
    bad = [
        "/search", "/s?", "/s/", "/browse", "/shop/",
        "/site/shop", "/category", "/c/", "/dept/",
        "/l/", "/b/", "?q=", "?k=", "?query=", "?keyword=",
    ]
    path_lower = href.lower()
    if any(b in path_lower for b in bad):
        return -1

    # Award points for URL path segments that reliably indicate a specific product page
    score = 0
    good = [
        "/dp/",          # Amazon
        "/ip/",          # Walmart
        "/product/",     # Best Buy, GameStop, many others
        "/products/",    # Shopify stores (Northerner, Nicokick)
        "/t/",           # Nike
        "/p/",           # Target, various
        "/item/",        # various
        "/buy/",         # various
        "/pd/",          # various
        "/skus/",        # various
        "/sku/",         # various
        "/itm/",         # eBay
        "/listing/",     # Etsy, various
        "/gl/",          # various product pages
        "/detail/",      # various
        "/pid/",         # various
        "/goods/",       # AliExpress-style
    ]
    for g in good:
        if g in path_lower:
            score += 10
            break

    # Paths containing a run of 4+ digits almost always include a product ID — strong positive signal
    import re as _re
    if _re.search(r"/\d{4,}", path):
        score += 5

    # Long human-readable slugs (e.g. /playstation-5-slim-console-digital-edition) indicate a real product page
    if len(path) > 30:
        score += 3

    return score


async def _find_direct_url(title: str, seller: str) -> Optional[str]:
    """
    Uses DuckDuckGo's site: operator to find the exact product page on the
    seller's website. Free, no API key, works for any retailer.

    For known sellers uses the KNOWN domain dict. For unknown sellers,
    resolves the domain via a DDG homepage search first (cached per process).
    Filters out homepages, search pages, and category pages.
    Prefers URLs with product-specific paths (/dp/, /ip/, /product/, etc.).
    """
    # Use the O(1) static dict lookup first; only hit DDG if the seller isn't recognized
    domain = _seller_domain(seller)
    if not domain:
        domain = await _resolve_seller_domain(seller)
    if not domain:
        return None

    query = f"{title} site:{domain}"

    try:
        def _ddg_search():
            from ddgs import DDGS
            # verify=False works around macOS LibreSSL TLS 1.3 handshake failures with DuckDuckGo
            with DDGS(verify=False) as ddgs:
                return list(ddgs.text(query, max_results=8))

        results = await asyncio.wait_for(
            asyncio.to_thread(_ddg_search),
            timeout=7.0,
        )

        domain_root = domain.replace("www.", "")
        candidates = []

        for r in results:
            href = r.get("href", "")
            if not href or domain_root not in href:
                continue
            score = _score_product_url(href)
            if score >= 0:
                candidates.append((score, href))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best = candidates[0][1]
            print(f"[DirectURL] DDG found ({candidates[0][0]}pts): {best[:80]}")
            return best

    except asyncio.TimeoutError:
        print(f"[DirectURL] DDG timed out for '{seller}'")
    except Exception as e:
        print(f"[DirectURL] DDG failed for '{seller}': {e}")

    return None


async def _channel3_direct_url(title: str, seller: str, api_key: str) -> Optional[str]:
    """
    Searches Channel3's 100M+ product database for this exact product.
    If found with an offer from the same seller, returns a buy.trychannel3.com
    link that redirects to the exact product page on that seller's site.

    Falls back to None if:
    - Channel3 doesn't carry this product (niche retailers like Northerner)
    - No offer matches the seller
    - API call fails
    """
    if not api_key:
        return None

    # Derive the seller's likely domain keyword (e.g. "Academy Sports + Outdoors" → "academy")
    seller_keyword = re.sub(r"[^a-z]", "", seller.lower().split()[0])

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                "https://api.trychannel3.com/v1/search",
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={"query": title},
            )
            if r.status_code != 200:
                return None

            data = r.json()
            products = data if isinstance(data, list) else data.get("products", data.get("results", []))

            for product in products[:10]:
                offers = product.get("offers", [])
                for offer in offers:
                    domain = offer.get("domain", "")
                    url = offer.get("url", "")
                    # Match seller keyword against the offer's domain
                    if seller_keyword and seller_keyword in domain and url:
                        print(f"[Channel3] Direct URL found for '{title[:40]}' via {domain}")
                        return url

    except Exception as e:
        print(f"[Channel3] URL lookup failed: {e}")

    return None


@router.post("/analyze")
async def analyze_product(req: AnalyzeRequest):
    """
    The "magic" intermediate page endpoint.

    Given a product + seller, returns:
    1. Price estimation (LightGBM)
    2. Product analysis (Claude AI)
    3. Seller analysis (Claude AI)
    4. Review highlights (DuckDuckGo + Google Places)
    5. Price history (90-day chart data)
    """
    from config import get_settings
    settings = get_settings()

    # Only run URL-discovery tasks when the incoming URL is just a Google search query (not a direct product link)
    needs_direct_url = bool(req.url and "google.com/search" in req.url)

    async def noop():
        return None

    # Run price estimation, review collection, and URL discovery in parallel so they don't block each other
    results = await asyncio.gather(
        get_price_estimator().estimate(
            base_price=req.price,
            source=req.source,
            seller=req.seller,
            is_local=req.source == "google_places",
        ),
        get_review_aggregator().get_reviews(
            product=req.title,
            seller=req.seller,
            google_place_id=req.google_place_id,
            google_api_key=settings.google_places_api_key,
        ),
        # DuckDuckGo site: search — free alternative to a paid URL-lookup API
        _find_direct_url(req.title, req.seller) if needs_direct_url else noop(),
        # Channel3 as a secondary lookup — covers retailers that DDG struggles to surface
        _channel3_direct_url(req.title, req.seller, settings.channel3_api_key)
        if needs_direct_url else noop(),
        return_exceptions=True,
    )

    price_data, reviews, ddg_url, channel3_url = results

    if isinstance(price_data, Exception):
        price_data = {"listed_price": req.price, "estimated_shipping": 0,
                      "estimated_hidden_fees": 0, "estimated_final": req.price,
                      "confidence": "Low", "savings_vs_estimate": 0,
                      "price_history": [], "data_note": "Estimation unavailable"}
    if isinstance(reviews, Exception):
        reviews = {"product_reviews": [], "seller_reviews": []}
    if isinstance(ddg_url, Exception):
        ddg_url = None
    if isinstance(channel3_url, Exception):
        channel3_url = None

    # Run Claude analysis after reviews are in hand so the prompts contain real review text
    ai_analysis = await get_claude_analyzer().analyze(
        product=req.title,
        seller=req.seller,
        price=req.price,
        source=req.source,
        product_reviews=reviews["product_reviews"],
        seller_reviews=reviews["seller_reviews"],
    )

    # Priority: DuckDuckGo direct page > Channel3 affiliate link > original URL
    if needs_direct_url:
        direct_url = ddg_url or channel3_url or req.url
    else:
        direct_url = req.url

    return {
        "price": price_data,
        "product_analysis": ai_analysis["product"],
        "seller_analysis": ai_analysis["seller"],
        "raw_reviews": {
            "product": reviews["product_reviews"][:5],
            "seller": reviews["seller_reviews"][:5],
        },
        "direct_url": direct_url,
    }
