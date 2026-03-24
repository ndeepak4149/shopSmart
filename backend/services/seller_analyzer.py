import asyncio
import json
import anthropic
from config import get_settings

settings = get_settings()


class SellerAnalyzer:
    """
    Batch-analyzes seller trustworthiness via a single Claude Haiku call.
    One call for all sellers in a search — much cheaper than per-seller calls.
    In-process cache so the same domain isn't re-analyzed in the same session.
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._cache: dict[str, dict] = {}

    async def analyze_batch(self, domains: list[str]) -> dict[str, dict]:
        """Returns trust/shipping/return scores for each domain. Uses cache for already-seen domains."""
        uncached = [d for d in domains if d not in self._cache]
        if uncached:
            results = await asyncio.to_thread(self._call_claude, uncached)
            self._cache.update(results)
        return {d: self._cache.get(d, self._default()) for d in domains}

    def _call_claude(self, domains: list[str]) -> dict:
        seller_list = "\n".join(f"- {d}" for d in domains)
        prompt = f"""Rate these online sellers for a US consumer purchase.
For each domain, return a JSON object with:
- trust_score (0.0-1.0): Overall trustworthiness and reliability
- shipping_score (0.0-1.0): Shipping speed and reliability
- return_score (0.0-1.0): Return policy generosity

Return ONLY a JSON object mapping domain to scores. No markdown.
Example: {{"amazon.com": {{"trust_score": 0.95, "shipping_score": 0.95, "return_score": 0.90}}}}

Sellers:
{seller_list}"""

        try:
            message = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except Exception as e:
            print(f"[SellerAnalyzer] Failed: {e}")
            return {d: self._default() for d in domains}

    @staticmethod
    def _default() -> dict:
        return {"trust_score": 0.5, "shipping_score": 0.5, "return_score": 0.5}
