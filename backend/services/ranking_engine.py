import re
import math
from dataclasses import dataclass
from typing import Optional
from agents.discovery_agent import RawListing


# Generic words that appear in almost every product listing and would pollute keyword matching scores
_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "in", "on", "at", "to", "of",
    "buy", "cheap", "best", "good", "new", "pack", "packs", "count",
    "free", "shipping", "online", "order", "sale", "deal",
    "pouches", "pouch", "product", "item", "brand", "size",
    # Broad category words — matching these against a title tells us nothing specific about relevance
    "nicotine", "tobacco", "cigarette", "headphone", "headphones",
    "laptop", "phone", "tablet", "watch", "shoe", "shoes", "bag",
    "supplement", "vitamin", "protein", "coffee", "tea",
}

# ── Seller trust tiers ────────────────────────────────────────────────────────
# HIGH     = verified major retailers and brand-direct online stores (+0.12)
# NEUTRAL  = established marketplaces where individual seller quality varies (±0.00)
# LOW      = grey-market, fast-fashion, or known low-quality sourcing (-0.05)
#
# Sellers not found in any list receive a slight positive benefit of the doubt (+0.04).

_HIGH_TRUST_SELLERS = {
    "amazon", "walmart", "target", "costco", "best buy", "bestbuy",
    "apple", "samsung", "sony", "microsoft", "dell", "hp", "lenovo",
    "nike", "adidas", "under armour", "underarmour",
    "home depot", "homedepot", "lowe's", "lowes",
    "chewy", "petco", "petsmart",
    "wayfair", "crate and barrel", "west elm", "pottery barn", "ikea",
    "nordstrom", "macy's", "macys", "gap", "old navy",
    "gamestop", "newegg", "b&h", "b&h photo", "adorama",
    "sephora", "ulta", "cvs", "walgreens",
    "rei", "patagonia", "columbia", "the north face", "north face",
    "guitar center", "guitarcenter", "sweetwater",
    "academy sports", "dick's sporting", "dicks sporting",
    "autozone", "advance auto", "o'reilly",
    "sam's club", "bj's", "costco",
    "foot locker", "footlocker", "finish line",
    "staples", "office depot",
    "nicokick", "northerner",
}

# Established marketplaces with variable third-party sellers — no bonus or penalty at the store level.
# Individual listing quality is judged separately via rating and review signals.
_NEUTRAL_TRUST_SELLERS = {
    "ebay", "etsy", "rakuten", "overstock", "poshmark",
    "mercari", "facebook marketplace", "offerup",
}

# Grey-market, fast-fashion, and counterfeit-prone platforms — penalised in ranking
_LOW_TRUST_SELLERS = {
    "wish", "aliexpress", "alibaba", "dhgate", "temu",
    "shein", "romwe", "zaful",
}


def _seller_trust_score(seller: str) -> tuple[float, Optional[str]]:
    """
    Returns (score adjustment, label or None).

    HIGH     → +0.12  "Trusted retailer"   (verified major retailers)
    NEUTRAL  →  0.00  no label             (established marketplaces like eBay, Etsy)
    LOW      → -0.05  "Unverified seller"  (grey-market / fast-fashion sites)
    UNKNOWN  → +0.04  no label             (benefit of the doubt)
    """
    lower = seller.lower().strip()

    for name in _HIGH_TRUST_SELLERS:
        if name in lower:
            return 0.12, "Trusted retailer"

    for name in _NEUTRAL_TRUST_SELLERS:
        if name in lower:
            return 0.00, None

    for name in _LOW_TRUST_SELLERS:
        if name in lower:
            return -0.05, "Unverified seller"

    # Unrecognized seller — award a small positive so new/niche retailers aren't unfairly buried
    return 0.04, None


@dataclass
class RankedListing:
    listing: RawListing
    score: float
    rank: int
    reason: str
    is_top_pick: bool = False
    value_score: int = 0
    explanation: str = ""


def _tokenize(text: str) -> set[str]:
    """Lowercase, split on non-alphanumeric, remove stopwords."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def _keyword_relevance(query_tokens: set[str], title: str, query: str) -> tuple[float, bool]:
    """
    Returns (score 0–1, is_relevant).

    is_relevant = False → excluded from Top Picks (pushed to All Results).

    Primary anchor = first meaningful word in the query (usually the brand).
    If it doesn't appear in the title, the listing is a different product.
    Partial matches get proportional credit (not binary).
    """
    title_tokens = _tokenize(title)
    if not query_tokens:
        return 0.5, True

    matched = query_tokens & title_tokens
    base_score = len(matched) / len(query_tokens)

    # The first meaningful word in the query is treated as the anchor (usually the brand or product name)
    ordered = [
        t for t in re.findall(r"[a-z0-9]+", query.lower())
        if t not in _STOPWORDS and len(t) > 1
    ]
    primary = ordered[0] if ordered else None

    if primary and primary not in title_tokens:
        # Anchor missing — give heavily discounted partial credit rather than a hard zero
        return base_score * 0.15, False

    # Reward listings that also match secondary query terms like model numbers or specs
    secondary_matches = len(matched) - (1 if primary and primary in matched else 0)
    if secondary_matches >= 2:
        base_score = min(base_score + 0.10, 1.0)

    return base_score, True


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _review_score(review_count: Optional[int]) -> float:
    """
    Logarithmic review count score (0–0.10).
    Avoids hard cutoffs — each 10× increase in reviews adds equal credit.
      10 reviews  → ~0.03
      100 reviews → ~0.05
      1000 reviews → ~0.08
      10000 reviews → ~0.10
    """
    if not review_count or review_count <= 0:
        return 0.0
    return min(math.log10(review_count) / 4.0, 1.0) * 0.10


def _compute_value_score(listing: RawListing, min_price: float, max_price: float) -> int:
    """0–100 score combining price, seller trust, rating, and reviews."""
    score = 0.0

    # Price competitiveness — cheapest listing gets full 35 pts
    if listing._raw_price and listing._raw_price > 0 and max_price > min_price:
        score += (1.0 - (listing._raw_price - min_price) / (max_price - min_price)) * 35
    else:
        score += 17

    # Seller trust
    trust_bonus, _ = _seller_trust_score(listing.seller_name)
    if trust_bonus >= 0.12:
        score += 25
    elif trust_bonus == 0.0:
        score += 15
    elif trust_bonus > 0:
        score += 12
    else:
        score += 5

    # Rating (0–25 pts)
    if listing.rating:
        score += (listing.rating / 5.0) * 25

    # Reviews — same log scale as _review_score but mapped to 15 pts
    if listing.review_count and listing.review_count > 0:
        score += min(math.log10(listing.review_count) / 4.0, 1.0) * 15

    return min(100, max(0, int(score)))


def _generate_explanation(
    listing: RawListing,
    total_count: int,
    price_ratio: Optional[float],
    is_cheapest: bool,
) -> str:
    """1-sentence human explanation for why a listing is a good pick."""
    trust_bonus, _ = _seller_trust_score(listing.seller_name)
    is_high_trust = trust_bonus >= 0.12

    rating_str = f"{listing.rating:.1f}★" if listing.rating else None
    reviews_str = f"{listing.review_count:,} reviews" if listing.review_count and listing.review_count >= 200 else None

    cond_prefix = ""
    if listing.condition and listing.condition != "new":
        cond_map = {"refurbished": "Refurbished", "open_box": "Open box", "used": "Used", "parts": "Parts only"}
        cond_prefix = cond_map.get(listing.condition, "") + " — "

    if is_cheapest and total_count > 1 and is_high_trust:
        return f"{cond_prefix}Lowest price across {total_count} results from a trusted retailer."
    if is_cheapest and total_count > 1:
        return f"{cond_prefix}Lowest price across {total_count} results."
    if price_ratio and price_ratio <= 0.82:
        savings = int((1 - price_ratio) * 100)
        suffix = " from a trusted retailer" if is_high_trust else ""
        return f"{cond_prefix}{savings}% below average price{suffix}."
    if rating_str and reviews_str and is_high_trust:
        return f"{cond_prefix}Trusted retailer — {rating_str} rating with {reviews_str}."
    if rating_str and reviews_str:
        return f"{cond_prefix}{rating_str} rating backed by {reviews_str}."
    if is_high_trust and rating_str:
        return f"{cond_prefix}Reliable retailer with a {rating_str} product rating."
    if rating_str and listing.rating and listing.rating >= 4.3:
        return f"{cond_prefix}Strong {rating_str} rating{(' with ' + reviews_str) if reviews_str else ''}."
    if is_high_trust:
        return f"{cond_prefix}Established retailer — generally reliable shopping experience."
    return f"{cond_prefix}Competitive option based on price and availability."


class RankingEngine:
    """
    Scores every listing across 7 signals:

    Signal                  Weight    Notes
    ─────────────────────── ───────── ────────────────────────────────────────
    1. Keyword relevance    0 – 0.30  Brand anchor must match; partial credit
    2. Price (normalised)   0 – 0.25  Lower is better; % savings vs median
    3. Seller trust         -0.05–0.12 Verified retailer vs marketplace seller
    4. Rating               0 – 0.15  Star rating, scaled
    5. Review count         0 – 0.10  Logarithmic — 10k reviews ≈ 2× credit of 10
    6. Deal detection       0 – 0.05  Price significantly below median = deal flag
    7. In-stock / local     0 – 0.08  Stock bonus + proximity for local stores
    """

    TOP_PICKS_COUNT = 8

    def rank_with_price_normalization(
        self,
        listings: list[RawListing],
        query: str = "",
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
    ) -> tuple[list[RankedListing], list[RankedListing]]:
        if not listings:
            return [], []

        query_tokens = _tokenize(query)

        # First pass: compute all signals except price (price normalization needs the full price range)
        scored = []
        for listing in listings:
            kw_score, is_relevant = _keyword_relevance(query_tokens, listing.title, query)
            base_score, reasons = self._score(listing, kw_score, user_lat, user_lon)
            scored.append((base_score, listing, reasons, is_relevant))

        # Second pass: replace the price placeholder with a properly normalized score and flag deals
        scored = self._normalize_prices(scored)

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Price range needed for value_score computation
        prices = [l._raw_price for _, l, _, _, _, _ in scored if l._raw_price and l._raw_price > 0]
        min_p = min(prices) if prices else 0.0
        max_p = max(prices) if prices else 0.0
        total_count = len(scored)

        # Build the two result buckets — keyword-irrelevant listings are demoted to the "rest" pile
        top_picks, rest = [], []
        rank = 1
        for score, listing, reasons, is_relevant, price_ratio, is_cheapest in scored:
            reason_text = " · ".join(reasons) if reasons else "Good option"
            is_top = is_relevant and rank <= self.TOP_PICKS_COUNT

            ranked = RankedListing(
                listing=listing,
                score=round(score, 4),
                rank=rank,
                reason=reason_text,
                is_top_pick=is_top,
                value_score=_compute_value_score(listing, min_p, max_p),
                explanation=_generate_explanation(listing, total_count, price_ratio, is_cheapest),
            )

            if is_top:
                top_picks.append(ranked)
            else:
                rest.append(ranked)

            rank += 1

        print(f"[Ranking] {len(top_picks)} top picks, {len(rest)} other results")
        return top_picks, rest

    # ── Scoring ────────────────────────────────────────────────────

    def _score(
        self,
        listing: RawListing,
        kw_score: float,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
    ) -> tuple[float, list[str]]:
        score = 0.0
        reasons = []

        # 1. Keyword relevance (0 – 0.30)
        score += kw_score * 0.30

        # 2. Temporary mid-range price placeholder — overwritten once _normalize_prices() has the full price range
        listing._raw_price = listing.price
        score += 0.125

        # 3. Seller trust (-0.05 – 0.12)
        trust_bonus, trust_label = _seller_trust_score(listing.seller_name)
        score += trust_bonus
        if trust_label:
            reasons.append(trust_label)

        # 4. Rating (0 – 0.15)
        if listing.rating:
            score += min(listing.rating / 5.0, 1.0) * 0.15
            if listing.rating >= 4.5:
                reasons.append("Highly rated")
            elif listing.rating >= 4.0:
                reasons.append("Well rated")

        # 5. Review count — logarithmic scale (0 – 0.10)
        rev_score = _review_score(listing.review_count)
        score += rev_score
        if listing.review_count and listing.review_count >= 1000:
            reasons.append(f"{listing.review_count:,} reviews")

        # 6. In-stock bonus (+0.05)
        if listing.in_stock:
            score += 0.05

        # 7. Local pickup + proximity bonus (0 – 0.08): rewards local stores, scaled by how close they are
        if listing.is_local:
            local_bonus = 0.04  # base bonus for being a physical store (pickup = no shipping wait)
            if user_lat and user_lon and listing.lat and listing.lon:
                dist_km = _haversine_km(user_lat, user_lon, listing.lat, listing.lon)
                # Linear decay: store at 0 km gets the full +0.04 proximity bonus, 50 km gets +0.0
                proximity = max(0.0, 1.0 - dist_km / 50.0) * 0.04
                local_bonus += proximity
                if dist_km < 5:
                    reasons.append(f"< 5 km away")
                elif dist_km < 20:
                    reasons.append(f"~{int(dist_km)} km away")
                else:
                    reasons.append("Available nearby")
            else:
                reasons.append("Available nearby")
            score += local_bonus

        return score, reasons

    def _normalize_prices(
        self,
        scored: list[tuple[float, RawListing, list[str], bool]],
    ) -> list[tuple[float, RawListing, list[str], bool, Optional[float], bool]]:
        prices = [
            l._raw_price for _, l, _, _ in scored
            if l._raw_price and l._raw_price > 0
        ]
        if not prices:
            return [(s, l, r, ir, None, False) for s, l, r, ir in scored]

        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price or 1

        sorted_prices = sorted(prices)
        q1 = sorted_prices[len(sorted_prices) // 4]
        q3 = sorted_prices[(3 * len(sorted_prices)) // 4]
        iqr_prices = [p for p in sorted_prices if q1 <= p <= q3] or sorted_prices
        mid = len(iqr_prices) // 2
        median_price = iqr_prices[mid]

        result = []
        for score, listing, reasons, is_relevant in scored:
            price_ratio: Optional[float] = None
            is_cheapest = False

            if listing._raw_price and listing._raw_price > 0:
                p = listing._raw_price
                price_score = (1.0 - (p - min_price) / price_range) * 0.25
                adjusted = score - 0.125 + price_score
                is_cheapest = (p == min_price and len(prices) > 1)

                if median_price > 0:
                    price_ratio = p / median_price

                    if price_ratio < 0.25:
                        is_relevant = False
                        adjusted -= 0.20
                        reasons = ["⚠ Price inconsistent with search"] + reasons
                    elif price_ratio < 0.50:
                        adjusted -= 0.12
                        reasons = ["Verify: unusually low price"] + reasons
                    elif price_ratio <= 0.80:
                        savings_pct = int((1 - price_ratio) * 100)
                        adjusted += 0.05
                        reasons = [f"Great deal ({savings_pct}% below avg)"] + reasons
                    elif is_cheapest:
                        reasons = ["Best price"] + reasons
            else:
                adjusted = score

            result.append((adjusted, listing, reasons, is_relevant, price_ratio, is_cheapest))

        return result
