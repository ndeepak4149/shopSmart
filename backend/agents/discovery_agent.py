import asyncio
import json
import math
import httpx
from dataclasses import dataclass, field
from typing import Optional
from config import get_settings

settings = get_settings()


@dataclass
class RawListing:
    """
    A single product listing from any source.
    This is the raw data before entity resolution and ranking.
    """
    title: str
    price: float
    url: str
    seller_name: str
    source: str                        # which data source produced this listing: 'channel3', 'google_shopping', 'google_places'
    image_url: Optional[str] = None
    is_local: bool = False             # True for Google Places results (physical stores shown on the map)
    lat: Optional[float] = None        # geographic coordinates — only set for local store listings
    lon: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    in_stock: bool = True
    shipping_info: Optional[str] = None
    stock_confidence: str = "unknown"  # how confident we are the product is in stock: 'high', 'medium', 'low', 'unknown'
    stock_note: str = ""               # short human-readable explanation shown in the map pin popup
    place_id: Optional[str] = None     # Google Places unique ID — used to deduplicate stores across multiple nearby searches
    distance_km: Optional[float] = None  # straight-line Haversine distance from the user's location in km
    condition: str = "new"             # 'new', 'refurbished', 'open_box', 'used', 'parts'
    price_verified: bool = True        # False for web-discovered sellers where price is unknown


def detect_condition(title: str) -> str:
    """
    Infers product condition from the listing title.
    Returns one of: 'new', 'refurbished', 'open_box', 'used', 'parts'
    """
    t = title.lower()
    if any(k in t for k in [
        "refurbished", "refurb", "renewed", "remanufactured",
        "certified pre-owned", "certified pre owned", "cpo",
        "factory reconditioned", "seller refurbished",
    ]):
        return "refurbished"
    if any(k in t for k in [
        "open box", "open-box", "openbox", "open item",
        "display model", "display unit", "demo unit", "floor model",
    ]):
        return "open_box"
    if any(k in t for k in [
        "used", "pre-owned", "pre owned", "preowned",
        "second hand", "secondhand", "second-hand", "like new",
        "very good", "good condition", "acceptable condition",
    ]):
        return "used"
    if any(k in t for k in [
        "for parts", "parts only", "not working", "as-is", "as is",
        "broken", "damaged", "faulty", "defective", "untested",
        "for repair",
    ]):
        return "parts"
    return "new"


class DiscoveryAgent:
    """
    Searches all data sources at the same time using async.
    If one source fails, the others still return results.
    """

    def __init__(self):
        self.channel3_key = settings.channel3_api_key
        self.ebay_app_id = settings.ebay_app_id
        self.ebay_client_id = settings.ebay_client_id
        self.google_key = settings.google_places_api_key
        self.serpapi_key = settings.serpapi_key

    async def search(
        self,
        query: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        city: Optional[str] = None
    ) -> list[RawListing]:
        """
        Main entry point. Runs all sources in parallel.
        Returns a flat list of all raw listings found.

        Sources:
        - Channel3: primary structured API (Amazon, BestBuy, niche sellers)
        - SerpAPI: Google Shopping results
        - eBay: used/refurbished market via Browse API (requires credentials)
        - Web Discovery: DuckDuckGo organic search for long-tail sellers
        - Google Places: physical stores within 50 miles (when location given)
        """
        tasks: list[tuple[str, object]] = [
            ("Channel3", self._channel3_search(query)),
            ("SerpAPI", self._serpapi_shopping_search(query)),
            ("WebDiscovery", self._web_discovery_search(query)),
        ]

        # eBay: only run if credentials are configured
        if self.ebay_client_id:
            tasks.append(("eBay", self._ebay_search(query)))

        # Local stores: only run if we have a location
        if lat and lon:
            tasks.append(("Google Places", self._google_places_search(query, lat, lon)))
        elif city:
            tasks.append(("Google Places", self._google_places_search_by_city(query, city)))

        task_names = [t[0] for t in tasks]
        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

        all_listings = []
        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                print(f"[Discovery] {name} failed: {result}")
                continue
            if isinstance(result, list):
                all_listings.extend(result)

        print(f"[Discovery] Found {len(all_listings)} total listings")
        return all_listings

    # ── Channel3 ─────────────────────────────────────────────────────────

    async def _channel3_search(self, query: str) -> list[RawListing]:
        """
        Channel3 is our primary source — covers Amazon, BestBuy,
        niche sellers, and local shops that Google Shopping misses.
        API docs: https://docs.trychannel3.com
        """
        url = "https://api.trychannel3.com/v0/search"
        headers = {
            "x-api-key": self.channel3_key,
            "Content-Type": "application/json"
        }
        payload = {"query": query}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            print(f"[Channel3] Status: {response.status_code}")
            if response.status_code == 402:
                print("[Channel3] Subscription not activated — using demo data")
                return self._demo_listings(query)
            if response.status_code != 200:
                print(f"[Channel3] Error body: {response.text[:300]}")
                return self._demo_listings(query)
            response.raise_for_status()
            data = response.json()

        # Channel3 API response is sometimes a bare list, sometimes wrapped in a 'products' or 'results' key
        if isinstance(data, list):
            products = data
        else:
            products = data.get("products", data.get("results", []))
        listings = []

        for item in products:
            try:
                # Channel3 returns price as either a number or a dict like {"price": 45.0, "currency": "USD"}
                raw_price = item.get("price", {})
                if isinstance(raw_price, dict):
                    price = float(raw_price.get("price", raw_price.get("value", 0)) or 0)
                else:
                    price = float(raw_price or 0)

                # image_url comes back as a plain string (not nested) — grab it directly
                image_url = item.get("image_url")

                # Normalize the availability field — Channel3 uses strings like "InStock" / "OutOfStock"
                availability = item.get("availability", "InStock")
                in_stock = str(availability).lower() not in ("outofstock", "out_of_stock", "unavailable")

                # Prefer the first offer's domain as the seller name; fall back to the brand_name field
                offers = item.get("offers", [])
                seller_name = item.get("brand_name", "Unknown")
                if offers and isinstance(offers, list):
                    seller_name = offers[0].get("domain", seller_name)

                raw_title = item.get("title", "")
                listing = RawListing(
                    title=raw_title,
                    price=price,
                    url=item.get("url", ""),
                    seller_name=seller_name,
                    source="channel3",
                    image_url=image_url,
                    in_stock=in_stock,
                    shipping_info=None,
                    rating=None,
                    review_count=None,
                    condition=detect_condition(raw_title),
                )
                if listing.price > 0 and listing.title:
                    listings.append(listing)
            except (ValueError, TypeError) as e:
                print(f"[Channel3] Skipping item due to error: {e}")
                continue

        print(f"[Channel3] {len(listings)} listings found")
        return listings

    # ── SerpAPI Google Shopping ───────────────────────────────────────────

    async def _serpapi_shopping_search(self, query: str) -> list[RawListing]:
        """
        Google Shopping via SerpAPI — returns real product listings with
        prices, images, ratings, and seller names. Same data as Google Shopping.
        """
        if not self.serpapi_key:
            print("[SerpAPI] No key set — skipping")
            return []
        try:
            results = await asyncio.to_thread(self._serpapi_fetch, query)
            listings = []
            for item in results:
                try:
                    price_raw = str(item.get("price", "0")).replace("$", "").replace(",", "").strip()
                    price = float(price_raw or 0)
                    title = item.get("title", "").strip()
                    if not title or price <= 0:
                        continue

                    # Rating and review count may be absent for newer or less-reviewed products
                    rating_info = item.get("rating")
                    reviews_info = item.get("reviews")

                    listing = RawListing(
                        title=title,
                        price=price,
                        url=item.get("best_url", item.get("link", item.get("product_link", ""))),
                        seller_name=item.get("source", item.get("store", "Online Store")),
                        source="google_shopping",
                        image_url=item.get("thumbnail"),
                        rating=float(rating_info) if rating_info else None,
                        review_count=int(str(reviews_info).replace(",", "")) if reviews_info else None,
                        in_stock=True,
                        shipping_info=item.get("shipping"),
                        condition=detect_condition(title),
                    )
                    listings.append(listing)
                except (ValueError, TypeError):
                    continue

            print(f"[SerpAPI] {len(listings)} listings found")
            return listings
        except Exception as e:
            print(f"[SerpAPI] Failed: {e}")
            return []

    def _serpapi_fetch(self, query: str) -> list[dict]:
        """Calls SerpAPI Google Shopping endpoint synchronously."""
        from serpapi import GoogleSearch
        search = GoogleSearch({
            "q": query,
            "tbm": "shop",
            "num": 20,
            "api_key": self.serpapi_key,
        })
        results = search.get_dict()
        items = results.get("shopping_results", [])

        # Build the best buyable URL for each result.
        # Google Shopping stopped returning direct merchant links, so we fall back to a
        # targeted Google search query that reliably surfaces the merchant's product page.
        import urllib.parse
        for item in items:
            direct = item.get("link") or ""
            title = item.get("title", query)
            seller = item.get("source", "")

            if direct and not direct.startswith("https://www.google.com"):
                # SerpAPI occasionally returns a real merchant URL — use it directly when available
                item["best_url"] = direct
            else:
                # Fall back to a targeted Google search — "{title} {seller}" — which reliably
                # surfaces the merchant's own product page as the top result
                search_q = urllib.parse.quote_plus(f"{title} {seller}")
                item["best_url"] = f"https://www.google.com/search?q={search_q}"

        return items

    # ── eBay Browse API ───────────────────────────────────────────────────

    async def _ebay_search(self, query: str) -> list[RawListing]:
        """
        eBay Browse API — covers used, refurbished, and fixed-price marketplace listings.
        Free tier: 5,000 calls/day.

        Requires eBay developer account (developer.ebay.com):
        1. Create a production application
        2. Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in .env and Railway env vars
        """
        from services.ebay_auth import EbayAuth

        token = await EbayAuth.get_token()
        if not token:
            return []

        async def _fetch(auth_token: str) -> dict:
            async with httpx.AsyncClient(timeout=15) as client:
                return await client.get(
                    "https://api.ebay.com/buy/browse/v1/item_summary/search",
                    params={
                        "q": query,
                        "filter": "buyingOptions:{FIXED_PRICE}",
                        "sort": "price",
                        "limit": 20,
                    },
                    headers={
                        "Authorization": f"Bearer {auth_token}",
                        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                    },
                )

        try:
            resp = await _fetch(token)

            if resp.status_code == 401:
                # Token expired mid-flight — clear and retry once
                EbayAuth._token = None
                token = await EbayAuth.get_token()
                if not token:
                    return []
                resp = await _fetch(token)

            if resp.status_code != 200:
                print(f"[eBay] API error: {resp.status_code}")
                return []

            data = resp.json()
            listings = []

            for item in data.get("itemSummaries", []):
                price = float(item.get("price", {}).get("value", 0))
                if price <= 0:
                    continue

                shipping_cost = 0.0
                shipping_opts = item.get("shippingOptions", [])
                if shipping_opts:
                    try:
                        shipping_cost = float(shipping_opts[0].get("shippingCost", {}).get("value", "0"))
                    except (ValueError, TypeError):
                        shipping_cost = 0.0

                condition_raw = item.get("condition", "New").lower()
                if "refurb" in condition_raw or "renewed" in condition_raw:
                    condition = "refurbished"
                elif "open" in condition_raw:
                    condition = "open_box"
                elif "used" in condition_raw or "pre-owned" in condition_raw:
                    condition = "used"
                else:
                    condition = "new"

                thumbnail_images = item.get("thumbnailImages") or []
                thumbnail = thumbnail_images[0].get("imageUrl") if thumbnail_images else None

                listings.append(RawListing(
                    title=item.get("title", query),
                    price=round(price + shipping_cost, 2),
                    url=item.get("itemWebUrl", ""),
                    seller_name=item.get("seller", {}).get("username", "eBay Seller"),
                    source="ebay",
                    image_url=thumbnail,
                    in_stock=True,
                    shipping_info=f"${shipping_cost:.2f} shipping" if shipping_cost > 0 else "Free shipping",
                    condition=condition,
                    price_verified=True,
                ))

            print(f"[eBay] {len(listings)} listings found")
            return listings

        except Exception as e:
            print(f"[eBay] Failed: {e}")
            return []

    # ── DuckDuckGo Web Discovery ──────────────────────────────────────────

    async def _web_discovery_search(self, query: str) -> list[RawListing]:
        """
        DuckDuckGo organic search for online sellers not covered by Channel3 or SerpAPI.
        Claude Haiku identifies legitimate seller pages — NO price estimation.

        Returned listings have price=0.0 and price_verified=False.
        They appear in results with "Visit site for price" instead of a dollar amount.
        They are NOT included in price-based ranking signals.
        """
        exclude = "amazon walmart bestbuy target ebay"
        search_query = f'"{query}" buy -{exclude}'

        try:
            def _search():
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    return list(ddgs.text(search_query, max_results=12))

            results = await asyncio.wait_for(asyncio.to_thread(_search), timeout=8.0)
            if not results:
                return []

            summaries = [
                f"{i}. {r.get('title', '')} | {r.get('href', '')} | {r.get('body', '')[:150]}"
                for i, r in enumerate(results[:12])
            ]

            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

            message = await asyncio.wait_for(asyncio.to_thread(
                client.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": (
                    f'Product: "{query}"\n\n'
                    f'Which of these search results are LEGITIMATE online stores where you can BUY this product?\n\n'
                    f'Reply with a JSON array. For each legitimate store include:\n'
                    f'- index (the result number)\n'
                    f'- seller_name (the store name)\n'
                    f'- is_trustworthy (true if it appears to be a real, established retailer)\n\n'
                    f'DO NOT estimate prices. Skip blogs, reviews, news, forums.\n'
                    f'If none are legitimate, return [].\n\n'
                    f'Results:\n' + '\n'.join(summaries)
                )}],
            ), timeout=12.0)

            text = message.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            evaluated = json.loads(text.strip())

            listings = []
            for item in evaluated:
                idx = item.get("index", -1)
                if 0 <= idx < len(results) and item.get("is_trustworthy", False):
                    listings.append(RawListing(
                        title=query,
                        price=0.0,
                        url=results[idx].get("href", ""),
                        seller_name=item.get("seller_name", "Online Store"),
                        source="web_discovery",
                        in_stock=True,
                        price_verified=False,
                    ))

            print(f"[WebDiscovery] {len(listings)} sellers found")
            return listings

        except Exception as e:
            print(f"[WebDiscovery] Failed: {e}")
            return []

    # ── Google Places (local stores) ──────────────────────────────────────

    def _get_store_types(self, query: str) -> list[str]:
        """
        Uses Claude to return 2–3 physical store types that would carry this product.
        Running parallel searches for each type casts a wider net.
        """
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            message = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=60,
                messages=[{
                    "role": "user",
                    "content": (
                        f"What types of physical retail stores would sell '{query}'? "
                        "Reply with 2-3 store types separated by commas, e.g. "
                        "'electronics store, department store, game store'. "
                        "Short phrases only, no explanation."
                    )
                }]
            )
            raw = message.content[0].text.strip().lower()
            types = [t.strip() for t in raw.split(",") if t.strip()][:3]
            print(f"[StoreTypes] '{query}' → {types}")
            return types if types else ["retail store"]
        except Exception as e:
            print(f"[StoreTypes] Claude unavailable, using fallback: {e}")
            return ["retail store"]

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Straight-line distance in km between two lat/lon points."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))

    # Known chain store names mapped to product keywords they reliably stock — used for confidence scoring
    CHAIN_CONFIDENCE = {
        # Nicotine / tobacco
        "cvs": ["nicotine", "tobacco", "velo", "zyn", "vape", "cigarette"],
        "walgreens": ["nicotine", "tobacco", "velo", "zyn", "vape", "cigarette"],
        "rite aid": ["nicotine", "tobacco", "velo", "zyn"],
        "7-eleven": ["nicotine", "tobacco", "velo", "zyn", "vape", "cigarette"],
        "circle k": ["nicotine", "tobacco", "velo", "zyn", "cigarette"],
        "wawa": ["nicotine", "tobacco", "cigarette"],
        # Electronics
        "best buy": ["phone", "laptop", "tablet", "headphone", "tv", "camera", "computer", "iphone"],
        "apple store": ["iphone", "macbook", "ipad", "airpods", "apple"],
        # General
        "target": ["nicotine", "phone", "laptop", "vitamin", "supplement", "toy", "shoe", "clothing"],
        "walmart": ["nicotine", "phone", "laptop", "vitamin", "supplement", "toy", "shoe", "clothing"],
        # Sports / outdoors
        "dick's sporting goods": ["yoga", "fitness", "gym", "sport", "outdoor", "camping", "shoe"],
        "rei": ["camping", "outdoor", "hiking", "yoga"],
        # Health
        "gnc": ["vitamin", "supplement", "protein"],
        "whole foods": ["vitamin", "supplement", "protein", "grocery"],
    }

    def _chain_confidence(self, store_name: str, query: str) -> Optional[str]:
        """Returns 'medium' if a known chain reliably carries this product type."""
        name = store_name.lower()
        q = query.lower()
        for chain, keywords in self.CHAIN_CONFIDENCE.items():
            if chain in name and any(k in q for k in keywords):
                return "medium"
        return None

    async def _serpapi_local_results(self, query: str, city: str) -> set[str]:
        """
        Searches SerpAPI for local businesses selling this product.
        Returns a set of store name keywords that appeared in results.
        Used to cross-reference with Google Places for high confidence.
        """
        if not self.serpapi_key:
            return set()
        try:
            def fetch():
                from serpapi import GoogleSearch
                s = GoogleSearch({
                    "q": f"{query} near {city}",
                    "location": city,
                    "api_key": self.serpapi_key,
                    "num": 10,
                })
                data = s.get_dict()
                names = set()
                for r in data.get("local_results", []):
                    title = r.get("title", "").lower()
                    for word in title.split():
                        if len(word) > 3:
                            names.add(word)
                return names
            return await asyncio.to_thread(fetch)
        except Exception as e:
            print(f"[SerpAPI Local] Failed: {e}")
            return set()

    async def _nearby_search_one(
        self, store_type: str, lat: float, lon: float, query: str
    ) -> list[dict]:
        """
        Single Nearby Search call using rankby=distance (no hard radius cap).
        Paginates up to 3 pages (60 results max) via next_page_token.
        Returns raw place dicts for the caller to filter and deduplicate.
        """
        base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{lat},{lon}",
            "rankby": "distance",
            "keyword": store_type,
            "key": self.google_key,
        }
        all_places = []
        async with httpx.AsyncClient(timeout=12.0) as client:
            for page in range(3):  # up to 3 pages = 60 results
                resp = await client.get(base_url, params=params)
                data = resp.json()
                all_places.extend(data.get("results", []))
                token = data.get("next_page_token")
                if not token:
                    break
                # Google's pagination token becomes valid only after a short server-side delay
                await asyncio.sleep(2)
                params = {"pagetoken": token, "key": self.google_key}
        return all_places

    def _filter_stores_sync(self, query: str, places: list[dict]) -> list[dict]:
        """
        Calls Claude Haiku with the full list of nearby stores and asks which ones
        would likely carry the searched product. Returns the relevant subset.
        Falls through to the full list if Claude is unavailable.
        """
        if not places:
            return places
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

            lines = []
            for i, p in enumerate(places):
                types_str = ", ".join(p.get("types", [])[:4])
                lines.append(f"{i}. {p.get('name', 'Store')} (types: {types_str})")
            store_list = "\n".join(lines)

            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                messages=[{
                    "role": "user",
                    "content": (
                        f"A user searched for \"{query}\".\n"
                        f"Which of these nearby stores would realistically carry this product?\n"
                        f"Reply with only the index numbers of relevant stores, comma-separated. "
                        f"Example: \"0,2,4\"\n\n"
                        f"Stores:\n{store_list}"
                    )
                }]
            )

            raw = message.content[0].text.strip()
            indices: set[int] = set()
            for part in raw.split(","):
                part = part.strip()
                if part.isdigit():
                    idx = int(part)
                    if 0 <= idx < len(places):
                        indices.add(idx)

            if not indices:
                return places  # Claude returned nothing parseable — keep all

            relevant = [places[i] for i in sorted(indices)]
            print(f"[StoreFilter] '{query}': {len(places)} → {len(relevant)} relevant stores")
            return relevant

        except Exception as e:
            print(f"[StoreFilter] Claude unavailable, keeping all stores: {e}")
            return places

    async def _filter_relevant_stores(self, query: str, places: list[dict]) -> list[dict]:
        """Async wrapper — runs the sync Claude filter in a thread."""
        return await asyncio.to_thread(self._filter_stores_sync, query, places)

    async def _google_places_search(
        self, query: str, lat: float, lon: float
    ) -> list[RawListing]:
        """
        Finds all physical stores within 50 miles (80 km) that likely carry the product.

        - Queries 2-3 store types in parallel (electronics store, game store, etc.)
        - Uses Nearby Search with rankby=distance (no hard radius cap)
        - Paginates up to 60 results per store type
        - Deduplicates by Google place_id
        - Filters to ≤ 80 km, checks product relevance with Claude, returns up to 30 stores
        """
        RADIUS_KM = 80.46  # 50 miles in km

        # Get store types in a thread (sync Claude call)
        store_types = await asyncio.to_thread(self._get_store_types, query)

        # Run all store type searches in parallel
        raw_results = await asyncio.gather(
            *[self._nearby_search_one(st, lat, lon, query) for st in store_types],
            return_exceptions=True,
        )

        # Collect deduplicated valid places (within radius, passes basic retailer check)
        seen_ids: set[str] = set()
        valid_places: list[dict] = []

        for result in raw_results:
            if isinstance(result, Exception):
                continue
            for place in result:
                pid = place.get("place_id", "")
                if pid and pid in seen_ids:
                    continue
                if pid:
                    seen_ids.add(pid)

                loc = place.get("geometry", {}).get("location", {})
                slat, slon = loc.get("lat"), loc.get("lng")
                if not slat or not slon:
                    continue

                dist = self._haversine_km(lat, lon, slat, slon)
                if dist > RADIUS_KM:
                    continue

                if not self._is_likely_retailer(place):
                    continue

                place["_dist_km"] = dist  # stash computed distance
                valid_places.append(place)

        # Ask Claude which of these stores would actually carry the product
        relevant_places = await self._filter_relevant_stores(query, valid_places)

        # Build RawListings from the filtered set
        listings: list[RawListing] = []
        for place in relevant_places:
            pid = place.get("place_id", "")
            loc = place.get("geometry", {}).get("location", {})
            slat, slon = loc.get("lat"), loc.get("lng")
            dist = place.get("_dist_km", 0.0)
            store_name = place.get("name", "Local Store")
            confidence, note = self._score_confidence(store_name, query, place)

            listings.append(RawListing(
                title=f"{store_name} — {query}",
                price=0.0,
                url=f"https://www.google.com/maps/place/?q=place_id:{pid}" if pid else "",
                seller_name=store_name,
                source="google_places",
                is_local=True,
                lat=slat,
                lon=slon,
                rating=place.get("rating"),
                review_count=place.get("user_ratings_total"),
                in_stock=True,
                stock_confidence=confidence,
                stock_note=note,
                place_id=pid,
                distance_km=round(dist, 2),
            ))

        # Sort by straight-line distance and cap at 30 stores to keep the map readable
        listings.sort(key=lambda l: l.distance_km or 999)
        print(f"[Google Places] {len(listings)} stores within 50 miles")
        return listings[:30]

    # Business types that are definitively NOT retail sellers
    _EXCLUDE_TYPES = {
        "lodging", "hospital", "school", "university", "bank",
        "atm", "parking", "airport", "subway_station", "transit_station",
        "church", "mosque", "synagogue", "hindu_temple",
        "restaurant", "cafe", "bar", "food", "bakery",
        "beauty_salon", "hair_care", "spa", "gym", "dentist", "doctor",
        "laundry", "car_wash", "car_repair", "storage",
        "accounting", "lawyer", "insurance_agency", "real_estate_agency",
        "moving_company", "electrician", "plumber", "locksmith",
        "painter", "roofing_contractor", "general_contractor",
    }

    # Keywords in store names that indicate non-retail (repair/service shops)
    _EXCLUDE_NAME_KEYWORDS = {
        "repair", "service", "clinic", "academy", "school", "tutoring",
        "salon", "spa", "massage", "dental", "medical", "law",
        "insurance", "realty", "mortgage", "bank", "credit union",
    }

    def _is_likely_retailer(self, place: dict) -> bool:
        """
        Returns False if the place is clearly not a product retailer
        (repair shop, service business, restaurant, etc.).
        """
        types = set(place.get("types", []))
        if types & self._EXCLUDE_TYPES:
            return False

        name = place.get("name", "").lower()
        if any(kw in name for kw in self._EXCLUDE_NAME_KEYWORDS):
            return False

        # Require enough reviews and a decent rating to weed out pop-ups and very new businesses
        rating = place.get("rating")
        review_count = place.get("user_ratings_total", 0)
        if rating and rating < 3.0:
            return False
        if review_count < 5:
            return False

        return True

    def _score_confidence(self, store_name: str, query: str, place: Optional[dict] = None) -> tuple[str, str]:
        """Returns (confidence, note) for a store + product combination."""
        chain_conf = self._chain_confidence(store_name, query)
        rating = (place or {}).get("rating") if place else None
        reviews = (place or {}).get("user_ratings_total", 0) if place else 0

        if chain_conf:
            # Known chain + good reviews → high confidence
            if rating and rating >= 4.0 and reviews >= 100:
                return "high", f"{store_name} reliably carries this product"
            return "medium", f"{store_name} typically stocks this product — call to confirm"

        return "low", "May carry this product — call ahead to confirm availability"

    def _demo_listings(self, query: str) -> list[RawListing]:
        """
        Placeholder listings displayed while the Channel3 subscription is being activated.
        These are replaced automatically once Channel3 starts returning real results.
        """
        return [
            RawListing(title=f"{query} — Amazon", price=299.99, url="https://amazon.com", seller_name="Amazon", source="channel3", rating=4.7, review_count=12400, in_stock=True, image_url=None),
            RawListing(title=f"{query} — Best Deal Online", price=274.00, url="https://bestbuy.com", seller_name="BestBuy", source="channel3", rating=4.5, review_count=3200, in_stock=True, image_url=None),
            RawListing(title=f"{query} — Open Box", price=229.99, url="https://ebay.com", seller_name="AudioDeals", source="channel3", rating=4.1, review_count=320, in_stock=True, image_url=None),
            RawListing(title=f"{query} — Certified Refurbished", price=199.99, url="https://walmart.com", seller_name="Walmart", source="channel3", rating=4.3, review_count=890, in_stock=True, image_url=None),
            RawListing(title=f"{query} — Limited Edition Bundle", price=349.99, url="https://target.com", seller_name="Target", source="channel3", rating=4.6, review_count=5600, in_stock=False, image_url=None),
            RawListing(title=f"{query} — Niche Seller Special", price=259.00, url="https://example-shop.com", seller_name="AudioNest", source="channel3", rating=4.8, review_count=145, in_stock=True, image_url=None),
            RawListing(title=f"{query} — Flash Sale", price=249.00, url="https://bhphotovideo.com", seller_name="B&H Photo", source="channel3", rating=4.9, review_count=22000, in_stock=True, image_url=None),
            RawListing(title=f"{query} — Student Discount", price=269.99, url="https://dell.com", seller_name="Dell", source="channel3", rating=4.4, review_count=1100, in_stock=True, image_url=None),
        ]

    async def _google_places_search_by_city(
        self, query: str, city: str
    ) -> list[RawListing]:
        """
        Fallback for when the user provides a city name but no GPS coordinates.
        Uses the Places Text Search endpoint (50 km radius) with multiple store type queries.
        """
        store_types = await asyncio.to_thread(self._get_store_types, query)
        text_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

        async def _text_search_one(store_type: str) -> list[dict]:
            params = {
                "query": f"{store_type} in {city}",
                "radius": 50000,
                "key": self.google_key,
            }
            places = []
            async with httpx.AsyncClient(timeout=12.0) as client:
                for _ in range(2):  # paginate up to 2 pages (40 results) per store type
                    resp = await client.get(text_url, params=params)
                    data = resp.json()
                    places.extend(data.get("results", []))
                    token = data.get("next_page_token")
                    if not token:
                        break
                    await asyncio.sleep(2)
                    params = {"pagetoken": token, "key": self.google_key}
            return places

        raw_results = await asyncio.gather(
            *[_text_search_one(st) for st in store_types],
            return_exceptions=True,
        )

        seen_ids: set[str] = set()
        valid_places: list[dict] = []
        for result in raw_results:
            if isinstance(result, Exception):
                continue
            for place in result:
                try:
                    pid = place.get("place_id", "")
                    if pid and pid in seen_ids:
                        continue
                    if pid:
                        seen_ids.add(pid)

                    location = place.get("geometry", {}).get("location", {})
                    slat, slon = location.get("lat"), location.get("lng")
                    if not slat or not slon:
                        continue

                    if not self._is_likely_retailer(place):
                        continue

                    valid_places.append(place)
                except (ValueError, TypeError):
                    continue

        # Ask Claude which of these stores would actually carry the product
        relevant_places = await self._filter_relevant_stores(query, valid_places)

        listings = []
        for place in relevant_places:
            pid = place.get("place_id", "")
            location = place.get("geometry", {}).get("location", {})
            slat, slon = location.get("lat"), location.get("lng")
            store_name = place.get("name", "Local Store")
            confidence, note = self._score_confidence(store_name, query, place)
            listings.append(RawListing(
                title=f"{store_name} — {query}",
                price=0.0,
                url=f"https://www.google.com/maps/place/?q=place_id:{pid}" if pid else "",
                seller_name=store_name,
                source="google_places",
                is_local=True,
                lat=slat,
                lon=slon,
                rating=place.get("rating"),
                review_count=place.get("user_ratings_total"),
                in_stock=True,
                stock_confidence=confidence,
                stock_note=note,
                place_id=pid,
            ))

        print(f"[Google Places] {len(listings)} local stores found (city search)")
        return listings
