import json
import re
import math
import random
from typing import Optional


# Hardcoded fee profiles used when the seller matches a known platform or as a last-resort fallback
_PLATFORM_DEFAULTS = {
    "ebay":           {"avg_shipping": 9.50, "shipping_std": 4.0, "fee_pct": 0.029, "tax_rate": 0.082, "accuracy": 0.74},
    "amazon":         {"avg_shipping": 0.00, "shipping_std": 2.5, "fee_pct": 0.00,  "tax_rate": 0.082, "accuracy": 0.97},
    "walmart":        {"avg_shipping": 5.99, "shipping_std": 1.5, "fee_pct": 0.00,  "tax_rate": 0.082, "accuracy": 0.95},
    "bestbuy":        {"avg_shipping": 0.00, "shipping_std": 0.5, "fee_pct": 0.00,  "tax_rate": 0.082, "accuracy": 0.98},
    "target":         {"avg_shipping": 0.00, "shipping_std": 1.0, "fee_pct": 0.00,  "tax_rate": 0.082, "accuracy": 0.96},
    "newegg":         {"avg_shipping": 4.99, "shipping_std": 3.0, "fee_pct": 0.00,  "tax_rate": 0.082, "accuracy": 0.92},
    "etsy":           {"avg_shipping": 6.50, "shipping_std": 4.0, "fee_pct": 0.065, "tax_rate": 0.082, "accuracy": 0.70},
    "google_shopping":{"avg_shipping": 6.50, "shipping_std": 4.5, "fee_pct": 0.015, "tax_rate": 0.082, "accuracy": 0.76},
    "google_places":  {"avg_shipping": 0.00, "shipping_std": 0.0, "fee_pct": 0.00,  "tax_rate": 0.082, "accuracy": 0.90},
    "channel3":       {"avg_shipping": 7.50, "shipping_std": 5.0, "fee_pct": 0.025, "tax_rate": 0.082, "accuracy": 0.78},
    "web":            {"avg_shipping": 8.00, "shipping_std": 5.0, "fee_pct": 0.022, "tax_rate": 0.082, "accuracy": 0.75},
    "default":        {"avg_shipping": 8.00, "shipping_std": 4.0, "fee_pct": 0.02,  "tax_rate": 0.082, "accuracy": 0.76},
}


class PriceEstimator:
    """
    Estimates the true final price a buyer pays for any seller.

    Asks Claude for seller-specific fee profiles (shipping, platform fees, tax),
    then applies them directly to compute the estimated final price.
    Seller profiles are cached in memory so Claude is only asked once per seller.
    """

    _seller_cache: dict = {}

    def __init__(self):
        pass

    async def estimate(
        self,
        base_price: float,
        source: str,
        seller: str = "",
        is_local: bool = False,
        title: str = "",
        **kwargs,
    ) -> dict:
        """
        Returns estimated final price with full breakdown.
        Fetches seller-specific fees via Claude if seller name is provided.
        """
        profile = await self._get_seller_profile(seller=seller, source=source)

        # direct formula: shipping + platform fee + sales tax + small noise
        shipping = 0.0 if is_local else max(0, random.gauss(profile["avg_shipping"], profile.get("shipping_std", 3.0)))
        hidden_fees = base_price * profile["fee_pct"] + base_price * profile["tax_rate"]
        fee_gap = shipping + hidden_fees
        estimated_final = round(base_price + fee_gap, 2)

        accuracy = profile["accuracy"]
        if accuracy >= 0.95:
            confidence = "High"
        elif accuracy >= 0.80:
            confidence = "Medium"
        else:
            confidence = "Low"

        seller_label = seller if seller else source

        # try to get real price history first; fall back to synthetic if not enough data yet
        price_history = await self._get_price_history(title, seller, base_price)

        return {
            "listed_price": base_price,
            "estimated_shipping": round(shipping, 2),
            "estimated_hidden_fees": round(hidden_fees, 2),
            "estimated_final": estimated_final,
            "confidence": confidence,
            "savings_vs_estimate": round(estimated_final - base_price, 2),
            "price_history": price_history,
            "data_note": profile.get(
                "note",
                f"Estimated using {seller_label} fee patterns. Includes shipping, platform fees, and sales tax."
            ),
        }

    # ── Seller profile resolution — static dict → Claude → platform default ─────────────

    async def _get_seller_profile(self, seller: str, source: str) -> dict:
        """
        Returns a fee profile for the seller. Uses Claude for unknown sellers,
        falls back to platform defaults if Claude fails or seller is empty.
        """
        cache_key = f"{seller.lower().strip()}|{source}"

        if cache_key in PriceEstimator._seller_cache:
            return PriceEstimator._seller_cache[cache_key]

        # Fast path: check static platform defaults before paying the latency cost of a Claude call
        source_key = source.lower()
        seller_lower = seller.lower()
        for known in _PLATFORM_DEFAULTS:
            if known in seller_lower or known in source_key:
                profile = _PLATFORM_DEFAULTS[known].copy()
                PriceEstimator._seller_cache[cache_key] = profile
                return profile

        # No match in static profiles — ask Claude for a fee estimate for this specific seller
        if seller:
            profile = await self._ask_claude_for_seller_fees(seller, source)
            if profile:
                PriceEstimator._seller_cache[cache_key] = profile
                return profile

        # Ultimate fallback if both static lookup and Claude call fail
        fallback = _PLATFORM_DEFAULTS.get(source, _PLATFORM_DEFAULTS["default"]).copy()
        PriceEstimator._seller_cache[cache_key] = fallback
        return fallback

    async def _ask_claude_for_seller_fees(self, seller: str, source: str) -> Optional[dict]:
        """
        Asks Claude haiku to estimate the fee structure for any given seller.
        Returns a profile dict or None if the call fails.
        """
        try:
            import anthropic
            from config import get_settings
            settings = get_settings()
            if not settings.anthropic_api_key:
                return None

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

            prompt = f"""You are a pricing expert. A user is buying from "{seller}" (found via {source}).

Estimate the EXTRA costs on top of the listed price a typical US buyer pays.
Respond ONLY with a JSON object — no markdown, no explanation.

{{
  "avg_shipping": <number in USD, 0 if usually free>,
  "fee_pct": <fraction like 0.029 for 2.9% platform/processing fee, 0 if none>,
  "tax_rate": 0.082,
  "accuracy": <0.0-1.0, how confident you are>,
  "note": "<one sentence explaining what charges apply>"
}}"""

            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text.strip()
            # Extract JSON from response
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return {
                    "avg_shipping": float(data.get("avg_shipping", 8.0)),
                    "shipping_std": 3.0,
                    "fee_pct": float(data.get("fee_pct", 0.02)),
                    "tax_rate": float(data.get("tax_rate", 0.082)),
                    "accuracy": float(data.get("accuracy", 0.75)),
                    "note": data.get("note", ""),
                }
        except Exception as e:
            print(f"[PriceEstimator] Claude seller lookup failed for '{seller}': {e}")

        return None

    # ── Price history — real data from Supabase, synthetic fallback ──────────────────────

    async def _get_price_history(self, title: str, seller: str, current_price: float) -> list[dict]:
        """
        Store the current price then fetch the last 90 days of snapshots from Supabase.
        Falls back to synthetic data if Supabase isn't set up or there's not enough history yet.
        """
        try:
            from services.database import get_db
            from datetime import datetime, timedelta

            product_key = title.lower().strip()[:200] if title else seller.lower().strip()
            if not product_key:
                return self._generate_price_history(current_price)

            db = get_db()

            # record this view as a price snapshot
            db.table("price_snapshots").insert({
                "product_key": product_key,
                "seller_name": seller.lower().strip() or "unknown",
                "source": "analyze",
                "price": current_price,
            }).execute()

            # pull up to 90 days of history back
            cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat()
            result = db.table("price_snapshots") \
                .select("price, recorded_at") \
                .eq("product_key", product_key) \
                .gte("recorded_at", cutoff) \
                .order("recorded_at", desc=True) \
                .limit(90) \
                .execute()

            rows = result.data or []
            # need at least 5 real data points to show a meaningful chart
            if len(rows) >= 5:
                history = [{"day": i, "price": float(r["price"])} for i, r in enumerate(rows)]
                history[0]["price"] = current_price  # ensure today's price is exact
                return history

        except Exception as e:
            print(f"[PriceHistory] Supabase unavailable, using synthetic: {e}")

        return self._generate_price_history(current_price)

    # ── Utilities — price history simulation and holiday proximity for seasonal context ───

    def _generate_price_history(self, current_price: float) -> list[dict]:
        history = []
        price = current_price * random.uniform(1.05, 1.20)
        for day in range(89, -1, -1):
            change = random.gauss(0, current_price * 0.01)
            price = max(current_price * 0.7, price + change)
            history.append({"day": day, "price": round(price, 2)})
        history[-1]["price"] = current_price
        return history

