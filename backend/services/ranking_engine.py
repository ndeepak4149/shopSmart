from dataclasses import dataclass, field
from typing import Optional
from agents.discovery_agent import RawListing


@dataclass
class RankedListing:
    """
    A listing after scoring — includes score and a human-readable reason
    so we can show the user WHY it's a top pick.
    """
    listing: RawListing
    score: float
    rank: int
    reason: str                        # e.g. "Best price · Highest rated"
    is_top_pick: bool = False


class RankingEngine:
    """
    Scores every listing across multiple signals and returns the top picks.

    Signals used:
    - Price (lower = better, relative to all results)
    - Seller rating (higher = better)
    - Similarity score (how well it matches the search)
    - Stock availability
    - Local pickup availability (bonus)
    - Review count (more reviews = more trustworthy)

    Phase 1: Rule-based scoring (works immediately)
    Phase 2: XGBoost model trained on real user clicks (added later)
    """

    TOP_PICKS_COUNT = 8       # how many top picks to surface

    def rank(
        self,
        listings: list[RawListing],
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
    ) -> tuple[list[RankedListing], list[RankedListing]]:
        """
        Returns (top_picks, rest) — two separate lists for the UI.
        Top picks go in the highlighted section, rest go below.
        """
        if not listings:
            return [], []

        scored = [self._score(listing) for listing in listings]

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        ranked = []
        for rank, (score, listing, reasons) in enumerate(scored, start=1):
            reason_text = " · ".join(reasons) if reasons else "Good option"
            is_top = rank <= self.TOP_PICKS_COUNT

            ranked.append(RankedListing(
                listing=listing,
                score=round(score, 4),
                rank=rank,
                reason=reason_text,
                is_top_pick=is_top,
            ))

        top_picks = [r for r in ranked if r.is_top_pick]
        rest = [r for r in ranked if not r.is_top_pick]

        print(f"[Ranking] {len(top_picks)} top picks, {len(rest)} other results")
        return top_picks, rest

    def _score(
        self,
        listing: RawListing,
    ) -> tuple[float, RawListing, list[str]]:
        """
        Scores a single listing. Returns (score, listing, reasons).
        Score is a number between 0 and 1.
        """
        score = 0.0
        reasons = []

        # ── Similarity score (0 - 0.35) ──────────────────────────────────
        # How well does this listing match the search query?
        similarity = getattr(listing, "similarity_score", 0.5)
        score += similarity * 0.35

        # ── Price score (0 - 0.30) ────────────────────────────────────────
        # We reward lower prices. Price score is handled relatively
        # after all listings are scored — using a placeholder here.
        # We'll normalize prices across all listings below.
        listing._raw_price = listing.price   # store for normalization step
        score += 0.15                        # placeholder, normalized later

        # ── Rating score (0 - 0.20) ───────────────────────────────────────
        if listing.rating:
            # Normalize: assume ratings are 0-5 scale
            rating_normalized = min(listing.rating / 5.0, 1.0)
            rating_contribution = rating_normalized * 0.20
            score += rating_contribution
            if listing.rating >= 4.5:
                reasons.append("Highly rated")
            elif listing.rating >= 4.0:
                reasons.append("Well rated")

        # ── Review count score (0 - 0.10) ────────────────────────────────
        # More reviews = more trustworthy seller
        if listing.review_count:
            if listing.review_count >= 1000:
                score += 0.10
                reasons.append("1000+ reviews")
            elif listing.review_count >= 100:
                score += 0.06
            elif listing.review_count >= 10:
                score += 0.03

        # ── Stock bonus (0 or 0.05) ───────────────────────────────────────
        if listing.in_stock:
            score += 0.05

        # ── Local pickup bonus (0 or 0.05) ────────────────────────────────
        if listing.is_local:
            score += 0.05
            reasons.append("Available nearby")

        return score, listing, reasons

    def normalize_prices(
        self,
        scored: list[tuple[float, RawListing, list[str]]]
    ) -> list[tuple[float, RawListing, list[str]]]:
        """
        After scoring everything, go back and normalize prices
        so the cheapest listing gets the full 0.30 price bonus.
        """
        prices = [
            listing._raw_price
            for _, listing, _ in scored
            if listing._raw_price and listing._raw_price > 0
        ]
        if not prices:
            return scored

        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price or 1  # avoid division by zero

        normalized = []
        for score, listing, reasons in scored:
            if listing._raw_price and listing._raw_price > 0:
                # Invert: lower price = higher score
                price_score = (
                    1.0 - (listing._raw_price - min_price) / price_range
                ) * 0.30
                # Replace the placeholder 0.15 with the real price score
                adjusted_score = score - 0.15 + price_score

                if listing._raw_price == min_price:
                    reasons = ["Best price"] + reasons
            else:
                adjusted_score = score

            normalized.append((adjusted_score, listing, reasons))

        return normalized

    def rank_with_price_normalization(
        self,
        listings: list[RawListing],
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
    ) -> tuple[list[RankedListing], list[RankedListing]]:
        """
        Full ranking with price normalization.
        Use this instead of rank() for production.
        """
        if not listings:
            return [], []

        # Filter out local store listings with no price for ranking
        # (they still appear but aren't scored on price)
        scored = [self._score(listing) for listing in listings]
        scored = self.normalize_prices(scored)
        scored.sort(key=lambda x: x[0], reverse=True)

        ranked = []
        for rank, (score, listing, reasons) in enumerate(scored, start=1):
            reason_text = " · ".join(reasons) if reasons else "Good option"
            is_top = rank <= self.TOP_PICKS_COUNT

            ranked.append(RankedListing(
                listing=listing,
                score=round(score, 4),
                rank=rank,
                reason=reason_text,
                is_top_pick=is_top,
            ))

        top_picks = [r for r in ranked if r.is_top_pick]
        rest = [r for r in ranked if not r.is_top_pick]

        print(f"[Ranking] {len(top_picks)} top picks, {len(rest)} other results")
        return top_picks, rest
