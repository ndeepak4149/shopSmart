import time
import base64
import httpx
from config import get_settings

settings = get_settings()


class EbayAuth:
    """
    eBay Browse API requires OAuth 2.0 client credentials.
    You cannot use ebay_app_id directly as a Bearer token.

    Setup:
    1. Register at developer.ebay.com (free)
    2. Create a production application
    3. Get your Client ID and Client Secret
    4. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to your .env and Railway env vars

    Token is cached in-process and refreshed automatically before expiry.
    """

    _token: str | None = None
    _expires_at: float = 0

    @classmethod
    async def get_token(cls) -> str | None:
        # Return cached token if still valid (with 60s buffer)
        if cls._token and time.time() < cls._expires_at - 60:
            return cls._token

        client_id = settings.ebay_client_id
        client_secret = settings.ebay_client_secret
        if not client_id or not client_secret:
            return None

        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.ebay.com/identity/v1/oauth2/token",
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": f"Basic {credentials}",
                    },
                    data={
                        "grant_type": "client_credentials",
                        "scope": "https://api.ebay.com/oauth/api_scope",
                    },
                )
                if resp.status_code != 200:
                    print(f"[eBay] OAuth failed: {resp.status_code} — {resp.text[:200]}")
                    return None

                data = resp.json()
                cls._token = data["access_token"]
                cls._expires_at = time.time() + data.get("expires_in", 7200)
                print(f"[eBay] OAuth token obtained, valid for {data.get('expires_in', '?')}s")
                return cls._token

        except Exception as e:
            print(f"[eBay] OAuth exchange failed: {e}")
            return None
