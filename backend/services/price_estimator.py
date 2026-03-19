import json
import re
import numpy as np
from typing import Optional
from datetime import datetime
import random
from sklearn.ensemble import GradientBoostingRegressor


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

    How it works:
    1. Ask Claude AI what the typical shipping, fees, and taxes are for THIS specific seller
       (works for ANY retailer — Target, B&H Photo, Etsy shops, local merchants, etc.)
    2. Feed those values into a GradientBoosting model trained on realistic transaction patterns
    3. Return a breakdown: listed price + shipping + platform fees + taxes = estimated final

    Seller profiles are cached in memory so Claude is only asked once per seller.
    """

    _model = None               # GradientBoosting model — trained once at startup and shared across all requests
    _seller_cache: dict = {}    # seller name → fee profile; cached per process so Claude is only called once per seller

    def __init__(self):
        if PriceEstimator._model is None:
            print("[PriceEstimator] Training model on seller fee patterns...")
            PriceEstimator._model = self._train_model()
            print("[PriceEstimator] Model ready")
        self.model = PriceEstimator._model

    async def estimate(
        self,
        base_price: float,
        source: str,
        seller: str = "",
        is_local: bool = False,
    ) -> dict:
        """
        Returns estimated final price with full breakdown.
        Fetches seller-specific fees via Claude if seller name is provided.
        """
        profile = await self._get_seller_profile(seller=seller, source=source)

        features = self._build_features(base_price, source, is_local, profile)
        fee_gap = float(self.model.predict([features])[0])
        fee_gap = max(0, fee_gap)

        # Decompose the total fee gap into shipping and other fees using the seller's known fee/shipping ratio
        total_non_shipping = base_price * profile["fee_pct"] + base_price * profile["tax_rate"]
        shipping = 0.0 if is_local else max(0, fee_gap - total_non_shipping)
        hidden_fees = max(0, fee_gap - shipping)
        estimated_final = round(base_price + fee_gap, 2)

        accuracy = profile["accuracy"]
        if accuracy >= 0.95:
            confidence = "High"
        elif accuracy >= 0.80:
            confidence = "Medium"
        else:
            confidence = "Low"

        seller_label = seller if seller else source
        return {
            "listed_price": base_price,
            "estimated_shipping": round(shipping, 2),
            "estimated_hidden_fees": round(hidden_fees, 2),
            "estimated_final": estimated_final,
            "confidence": confidence,
            "savings_vs_estimate": round(estimated_final - base_price, 2),
            "price_history": self._generate_price_history(base_price),
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

    # ── ML model — trained on synthetic transactions to predict total hidden fees ─────────

    def _build_features(self, base_price, source, is_local, profile):
        now = datetime.now()
        return [
            base_price,
            profile["avg_shipping"],
            profile["fee_pct"],
            profile["tax_rate"],
            profile["accuracy"],
            now.weekday(),
            self._days_to_next_holiday(now),
            1 if is_local else 0,
            np.log1p(base_price),
            base_price * profile["fee_pct"],
            base_price * profile["tax_rate"],
            0.0 if is_local else profile["avg_shipping"],
        ]

    def _train_model(self) -> GradientBoostingRegressor:
        """
        Train on 10000 synthetic transactions covering a wide range of sellers.
        Each transaction simulates: shipping + platform fee + sales tax + noise.
        """
        random.seed(42)
        np.random.seed(42)

        profiles = list(_PLATFORM_DEFAULTS.values())
        X, y = [], []

        for _ in range(10000):
            profile = random.choice(profiles)
            base_price = random.uniform(3, 3000)
            is_local = profile["avg_shipping"] == 0 and profile["fee_pct"] == 0

            features = self._build_features(base_price, "synthetic", is_local, profile)

            shipping = 0.0 if is_local else max(
                0, random.gauss(profile["avg_shipping"], profile.get("shipping_std", 3.0))
            )
            platform_fee = base_price * profile["fee_pct"]
            # Vary tax rate across the realistic US state range (4% low-tax states to 10.5% high-tax)
            tax = base_price * random.uniform(0.04, 0.105)
            noise = random.gauss(0, 1.0)
            true_gap = max(0, shipping + platform_fee + tax + noise)

            X.append(features)
            y.append(true_gap)

        model = GradientBoostingRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=4,
            random_state=42,
        )
        model.fit(np.array(X), np.array(y))
        return model

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

    def _days_to_next_holiday(self, now: datetime) -> int:
        holidays = [
            datetime(now.year, 11, 29),  # Black Friday
            datetime(now.year, 12, 25),  # Christmas
            datetime(now.year, 7, 4),    # July 4th
            datetime(now.year, 11, 11),  # Veterans Day
        ]
        days = []
        for h in holidays:
            diff = (h - now).days
            if diff < 0:
                diff += 365
            days.append(diff)
        return min(days)
