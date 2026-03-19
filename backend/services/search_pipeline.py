from typing import Optional
from agents.discovery_agent import DiscoveryAgent, RawListing
from services.ranking_engine import RankingEngine, RankedListing


class SearchPipeline:
    """
    Orchestrates the full search flow:
    Discovery → Ranking → Response

    This is what gets called when a user searches for a product.
    """

    def __init__(self):
        self.discovery = DiscoveryAgent()
        self.ranker = RankingEngine()

    async def search(
        self,
        query: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        city: Optional[str] = None,
    ) -> dict:
        """
        Full search pipeline. Returns a dict ready to send to the frontend.

        Flow:
        1. Discovery Agent searches all sources in parallel
        2. Ranking Engine picks the top 8 picks
        3. Return structured response
        """

        # Step 1: Fan out to all data sources (Channel3, SerpAPI, Google Places) simultaneously
        print(f"\n[Pipeline] Searching for: '{query}'")
        raw_listings = await self.discovery.search(
            query=query,
            lat=lat,
            lon=lon,
            city=city,
        )

        if not raw_listings:
            return {
                "query": query,
                "top_picks": [],
                "other_results": [],
                "local_stores": [],
                "total_found": 0,
            }

        # Step 2: Split local store results from online listings — local stores go to the map panel
        local_stores = [l for l in raw_listings if l.is_local]
        online_listings = [l for l in raw_listings if not l.is_local]

        # Step 3: Narrow to top 30 cheapest before ranking so the scorer works on a manageable set
        all_listings = sorted(
            online_listings,
            key=lambda l: (l.price if l.price > 0 else float("inf"))
        )[:30]

        top_picks, rest = self.ranker.rank_with_price_normalization(
            listings=all_listings,
            query=query,
            user_lat=lat,
            user_lon=lon,
        )

        # Step 4: Format all results into clean dicts the frontend can consume directly
        return {
            "query": query,
            "top_picks": [self._format(r) for r in top_picks],
            "other_results": [self._format(r) for r in rest],
            "local_stores": [self._format_local(s) for s in local_stores],
            "total_found": len(raw_listings),
        }

    def _format(self, ranked: RankedListing) -> dict:
        """Converts a RankedListing into a clean dict for the frontend."""
        l = ranked.listing
        return {
            "id": f"{l.source}_{hash(l.url)}",
            "title": l.title,
            "price": l.price,
            "url": l.url,
            "seller_name": l.seller_name,
            "source": l.source,
            "image_url": l.image_url,
            "rating": l.rating,
            "review_count": l.review_count,
            "in_stock": l.in_stock,
            "shipping_info": l.shipping_info,
            "is_local": l.is_local,
            "lat": l.lat,
            "lon": l.lon,
            "rank": ranked.rank,
            "score": ranked.score,
            "reason": ranked.reason,
            "is_top_pick": ranked.is_top_pick,
            "condition": l.condition,
        }

    def _format_local(self, listing: RawListing) -> dict:
        """Formats a local store listing for the map."""
        return {
            "name": listing.seller_name,
            "lat": listing.lat,
            "lon": listing.lon,
            "rating": listing.rating,
            "review_count": listing.review_count,
            "source": listing.source,
            "stock_confidence": listing.stock_confidence,
            "stock_note": listing.stock_note,
            "distance_km": listing.distance_km,
            "maps_url": listing.url or None,
            "place_id": listing.place_id,
        }
