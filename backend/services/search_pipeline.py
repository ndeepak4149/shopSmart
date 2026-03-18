from typing import Optional
from agents.discovery_agent import DiscoveryAgent, RawListing
from services.entity_resolution import EntityResolver
from services.ranking_engine import RankingEngine, RankedListing


class SearchPipeline:
    """
    Orchestrates the full search flow:
    Discovery → Entity Resolution → Ranking → Response

    This is what gets called when a user searches for a product.
    """

    def __init__(self):
        self.discovery = DiscoveryAgent()
        self.resolver = EntityResolver()
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
        2. Entity Resolver groups same products together
        3. Ranking Engine picks the top 8 picks
        4. Return structured response
        """

        # Step 1: Discover all listings from all sources
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

        # Step 2: Separate local stores (map pins) from online listings
        local_stores = [l for l in raw_listings if l.is_local]
        online_listings = [l for l in raw_listings if not l.is_local]

        # Step 3: Entity resolution on online listings only
        resolved = self.resolver.resolve(query, online_listings)

        # Step 4: Rank the exact matches (these are the main results)
        all_matched = [listing for listing, _ in resolved.exact]

        # Also include top related items if we don't have enough results
        if len(all_matched) < 8:
            related_listings = [
                listing for listing, _ in resolved.related
            ]
            all_matched.extend(related_listings)

        top_picks, rest = self.ranker.rank_with_price_normalization(
            listings=all_matched,
            user_lat=lat,
            user_lon=lon,
        )

        # Step 5: Format for the frontend
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
        }
