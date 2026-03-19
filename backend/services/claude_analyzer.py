import anthropic
from config import get_settings

settings = get_settings()


class ClaudeAnalyzer:
    """
    Uses Claude API to generate:
    1. Product analysis — what is it, who it's for, pros/cons
    2. Seller analysis — trustworthiness, reputation, customer experience
    3. Review summary — what real customers are saying (product + seller)
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def analyze(
        self,
        product: str,
        seller: str,
        price: float,
        source: str,
        product_reviews: list[dict],
        seller_reviews: list[dict],
    ) -> dict:
        """
        Run product and seller analysis in parallel using Claude.
        Returns structured summaries for both.
        """
        import asyncio

        product_task = asyncio.to_thread(
            self._product_analysis,
            product=product,
            seller=seller,
            price=price,
            reviews=product_reviews,
        )
        seller_task = asyncio.to_thread(
            self._seller_analysis,
            seller=seller,
            product=product,
            source=source,
            reviews=seller_reviews,
        )

        results = await asyncio.gather(product_task, seller_task, return_exceptions=True)

        product_result = results[0] if not isinstance(results[0], Exception) else self._fallback_product(product)
        seller_result  = results[1] if not isinstance(results[1], Exception) else self._fallback_seller(seller)

        return {
            "product": product_result,
            "seller": seller_result,
        }

    # ── Product Analysis — structured JSON prompt so the response is always parseable ──

    def _product_analysis(
        self,
        product: str,
        seller: str,
        price: float,
        reviews: list[dict],
    ) -> dict:
        review_text = self._format_reviews(reviews) if reviews else "No external reviews found."

        prompt = f"""You are a product analyst helping shoppers make smart decisions.

Product: {product}
Sold by: {seller}
Listed price: ${price:.2f}

Customer reviews and discussions found online:
{review_text}

Provide a structured product analysis with exactly this JSON format:
{{
  "verdict": "one sentence bottom-line verdict (is it worth it at this price?)",
  "pros": ["pro 1", "pro 2", "pro 3"],
  "cons": ["con 1", "con 2", "con 3"],
  "who_its_for": "1-2 sentences describing who this product is ideal for",
  "value_rating": "excellent|good|fair|poor",
  "review_highlights": [
    {{"source": "source name", "text": "brief quote or insight from a review", "sentiment": "positive|neutral|negative"}},
    {{"source": "source name", "text": "brief quote or insight from a review", "sentiment": "positive|neutral|negative"}},
    {{"source": "source name", "text": "brief quote or insight from a review", "sentiment": "positive|neutral|negative"}}
  ]
}}

Be specific and cite what reviewers actually said. If no reviews are available, give your best analysis based on general knowledge of the product.
Respond with valid JSON only, no markdown."""

        message = self.client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        text = message.content[0].text.strip()
        # Strip markdown fences (```json ... ```) that Claude sometimes wraps around JSON
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())

    # ── Seller Analysis — same structured approach as product analysis ──────────────────

    def _seller_analysis(
        self,
        seller: str,
        product: str,
        source: str,
        reviews: list[dict],
    ) -> dict:
        review_text = self._format_reviews(reviews) if reviews else "No seller reviews found."

        prompt = f"""You are a shopping advisor helping customers evaluate where to buy from.

Seller/Store: {seller}
Platform/Source: {source}
Product being purchased: {product}

Customer reviews and feedback about this seller found online:
{review_text}

Provide a structured seller analysis with exactly this JSON format:
{{
  "verdict": "one sentence verdict on whether this is a trustworthy place to buy from",
  "trust_score": "high|medium|low",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "watch_out_for": ["thing to watch out for 1", "thing to watch out for 2"],
  "shipping_reputation": "brief note on their shipping speed/reliability",
  "return_policy_note": "brief note on their return policy reputation",
  "customer_feedback": [
    {{"source": "source name", "text": "what customers say about this seller", "sentiment": "positive|neutral|negative"}},
    {{"source": "source name", "text": "what customers say about this seller", "sentiment": "positive|neutral|negative"}},
    {{"source": "source name", "text": "what customers say about this seller", "sentiment": "positive|neutral|negative"}}
  ]
}}

Base your analysis on the reviews provided. If limited info is available, give reasonable insights based on general knowledge of the seller/platform.
Respond with valid JSON only, no markdown."""

        message = self.client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())

    # ── Helpers — shared utilities for prompt building and fallback responses ───────────

    def _format_reviews(self, reviews: list[dict]) -> str:
        lines = []
        for i, r in enumerate(reviews[:8], 1):
            source = r.get("source", "Web")
            text = r.get("text", "")[:300]
            lines.append(f"{i}. [{source}] {text}")
        return "\n".join(lines)

    def _fallback_product(self, product: str) -> dict:
        return {
            "verdict": f"Analysis unavailable for {product}. Check seller reviews and compare prices before buying.",
            "pros": ["Check product specifications", "Compare with alternatives", "Read buyer reviews"],
            "cons": ["Could not load AI analysis", "Verify return policy", "Check shipping costs"],
            "who_its_for": "Please research this product independently for personalized recommendations.",
            "value_rating": "fair",
            "review_highlights": [],
        }

    def _fallback_seller(self, seller: str) -> dict:
        return {
            "verdict": f"Could not load analysis for {seller}. Research independently before purchasing.",
            "trust_score": "medium",
            "strengths": ["Verify seller credentials", "Check return policy", "Read recent reviews"],
            "watch_out_for": ["Unusually low prices", "No return policy", "Limited contact info"],
            "shipping_reputation": "Unknown — check seller page for shipping details.",
            "return_policy_note": "Unknown — verify return policy before purchasing.",
            "customer_feedback": [],
        }
