import asyncio
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
    source: str                        # 'channel3', 'ebay', 'google_places'
    image_url: Optional[str] = None
    is_local: bool = False             # physical store?
    lat: Optional[float] = None        # store location (for map)
    lon: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    in_stock: bool = True
    shipping_info: Optional[str] = None


class DiscoveryAgent:
    """
    Searches all data sources at the same time using async.
    If one source fails, the others still return results.
    """

    def __init__(self):
        self.channel3_key = settings.channel3_api_key
        self.ebay_app_id = settings.ebay_app_id
        self.google_key = settings.google_places_api_key

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
        """
        tasks = [
            self._channel3_search(query),
            self._ebay_search(query),
        ]

        # Only search local stores if we have a location
        if lat and lon:
            tasks.append(self._google_places_search(query, lat, lon))
        elif city:
            tasks.append(self._google_places_search_by_city(query, city))

        # Run all tasks at the same time, don't crash if one fails
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten all results into one list, skip any that errored
        all_listings = []
        source_names = ["Channel3", "eBay", "Google Places"]
        for i, result in enumerate(results):
            source = source_names[i] if i < len(source_names) else "Unknown"
            if isinstance(result, Exception):
                print(f"[Discovery] {source} failed: {result}")
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

        # Channel3 returns either a list directly or a dict with 'products'
        if isinstance(data, list):
            products = data
        else:
            products = data.get("products", data.get("results", []))
        listings = []

        for item in products:
            try:
                # Price is a dict: {"price": 45.0, "currency": "USD"}
                raw_price = item.get("price", {})
                if isinstance(raw_price, dict):
                    price = float(raw_price.get("price", raw_price.get("value", 0)) or 0)
                else:
                    price = float(raw_price or 0)

                # image_url is a direct string field
                image_url = item.get("image_url")

                # Availability: "InStock" or "OutOfStock"
                availability = item.get("availability", "InStock")
                in_stock = str(availability).lower() not in ("outofstock", "out_of_stock", "unavailable")

                # Seller: use first offer's domain, or brand name
                offers = item.get("offers", [])
                seller_name = item.get("brand_name", "Unknown")
                if offers and isinstance(offers, list):
                    seller_name = offers[0].get("domain", seller_name)

                listing = RawListing(
                    title=item.get("title", ""),
                    price=price,
                    url=item.get("url", ""),
                    seller_name=seller_name,
                    source="channel3",
                    image_url=image_url,
                    in_stock=in_stock,
                    shipping_info=None,
                    rating=None,
                    review_count=None,
                )
                if listing.price > 0 and listing.title:
                    listings.append(listing)
            except (ValueError, TypeError) as e:
                print(f"[Channel3] Skipping item due to error: {e}")
                continue

        print(f"[Channel3] {len(listings)} listings found")
        return listings

    # ── eBay ─────────────────────────────────────────────────────────────

    async def _ebay_search(self, query: str) -> list[RawListing]:
        """
        eBay requires OAuth2 token exchange — skipped for Phase 1.
        Channel3 already covers eBay listings.
        """
        print("[eBay] Skipped — covered by Channel3")
        return []

    # ── Google Places (local stores) ──────────────────────────────────────

    async def _google_places_search(
        self, query: str, lat: float, lon: float
    ) -> list[RawListing]:
        """
        Finds physical stores near the user that likely carry the product.
        These show up as pins on the map.
        """
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": f"{query} store near me",
            "location": f"{lat},{lon}",
            "radius": 20000,           # 20km radius
            "key": self.google_key,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        listings = []
        for place in data.get("results", [])[:10]:
            try:
                location = place.get("geometry", {}).get("location", {})
                listing = RawListing(
                    title=f"{place.get('name', '')} — {query}",
                    price=0.0,          # price unknown for physical stores
                    url="",
                    seller_name=place.get("name", "Local Store"),
                    source="google_places",
                    is_local=True,
                    lat=location.get("lat"),
                    lon=location.get("lng"),
                    rating=place.get("rating"),
                    review_count=place.get("user_ratings_total"),
                    in_stock=True,
                )
                if listing.lat and listing.lon:
                    listings.append(listing)
            except (ValueError, TypeError):
                continue

        print(f"[Google Places] {len(listings)} local stores found")
        return listings

    def _demo_listings(self, query: str) -> list[RawListing]:
        """
        Demo listings shown while Channel3 subscription is being activated.
        Replace with real data once Channel3 is live.
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
        Same as above but uses city name instead of coordinates.
        Used when the user types their city instead of sharing GPS location.
        """
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": f"{query} store in {city}",
            "key": self.google_key,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        listings = []
        for place in data.get("results", [])[:10]:
            try:
                location = place.get("geometry", {}).get("location", {})
                listing = RawListing(
                    title=f"{place.get('name', '')} — {query}",
                    price=0.0,
                    url="",
                    seller_name=place.get("name", "Local Store"),
                    source="google_places",
                    is_local=True,
                    lat=location.get("lat"),
                    lon=location.get("lng"),
                    rating=place.get("rating"),
                    review_count=place.get("user_ratings_total"),
                    in_stock=True,
                )
                if listing.lat and listing.lon:
                    listings.append(listing)
            except (ValueError, TypeError):
                continue

        print(f"[Google Places] {len(listings)} local stores found (city search)")
        return listings
