import asyncio
import httpx
from typing import Optional
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


class ReviewAggregator:
    """
    Fetches real reviews from:
    1. DuckDuckGo search (no API key needed)
    2. Google Places (for local stores)

    Returns raw review snippets for Claude to summarize.
    """

    async def get_reviews(
        self,
        product: str,
        seller: str,
        google_place_id: Optional[str] = None,
        google_api_key: Optional[str] = None,
    ) -> dict:
        tasks = [
            asyncio.to_thread(self._ddg_product_reviews, product, seller),
            asyncio.to_thread(self._ddg_seller_reviews, seller, product),
        ]

        if google_place_id and google_api_key:
            tasks.append(
                self._google_place_reviews(google_place_id, google_api_key)
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        product_reviews = results[0] if not isinstance(results[0], Exception) else []
        seller_reviews  = results[1] if not isinstance(results[1], Exception) else []
        google_reviews  = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else []

        return {
            "product_reviews": product_reviews,
            "seller_reviews": seller_reviews + google_reviews,
        }

    # ── DuckDuckGo helpers — run in threads because the DDGS client is synchronous ──────

    def _ddg_product_reviews(self, product: str, seller: str) -> list[dict]:
        """Search DuckDuckGo for product reviews from Reddit and consumer review sites."""
        snippets = []
        queries = [
            f"{product} review reddit",
            f"{product} worth buying honest review",
            f"is {product} good review",
        ]
        for q in queries:
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(q, max_results=4))
                for r in results:
                    body = r.get("body", "").strip()
                    if len(body) > 40:
                        snippets.append({
                            "source": self._detect_source(r.get("href", "")),
                            "text": body[:400],
                            "url": r.get("href", ""),
                            "title": r.get("title", ""),
                        })
            except Exception:
                pass
        return snippets[:10]

    def _ddg_seller_reviews(self, seller: str, product: str) -> list[dict]:
        """Search DuckDuckGo for customer experiences with this seller or store."""
        snippets = []
        queries = [
            f"{seller} store review trustworthy",
            f"buy from {seller} experience review",
            f"{seller} {product} customer experience",
        ]
        for q in queries:
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(q, max_results=4))
                for r in results:
                    body = r.get("body", "").strip()
                    if len(body) > 40:
                        snippets.append({
                            "source": self._detect_source(r.get("href", "")),
                            "text": body[:400],
                            "url": r.get("href", ""),
                            "title": r.get("title", ""),
                        })
            except Exception:
                pass
        return snippets[:8]

    async def _google_place_reviews(self, place_id: str, api_key: str) -> list[dict]:
        """Fetch up to 5 Google Places reviews for a physical store using its place_id."""
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "reviews,rating,user_ratings_total",
            "key": api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(url, params=params)
                data = resp.json()
            reviews = data.get("result", {}).get("reviews", [])
            return [
                {
                    "source": "Google",
                    "text": r.get("text", ""),
                    "rating": r.get("rating"),
                    "author": r.get("author_name", ""),
                }
                for r in reviews
                if r.get("text")
            ]
        except Exception:
            return []

    def _detect_source(self, url: str) -> str:
        if "reddit.com" in url:
            return "Reddit"
        if "trustpilot" in url:
            return "Trustpilot"
        if "yelp.com" in url:
            return "Yelp"
        if "amazon.com" in url:
            return "Amazon"
        if "bestbuy.com" in url:
            return "BestBuy"
        return "Web"
