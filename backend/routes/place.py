import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

# Fields requested from the Places Details API — all in the Basic tier so they don't incur extra billing
_FIELDS = ",".join([
    "name",
    "formatted_address",
    "formatted_phone_number",
    "opening_hours",
    "website",
    "rating",
    "user_ratings_total",
    "price_level",
    "photos",
    "business_status",
])


@router.get("/place/{place_id}")
async def get_place_details(place_id: str):
    """
    Fetches rich details for a Google Places location.
    Called lazily when the user opens a store pin popup on the map.

    Returns: address, phone, hours (open now + weekday text), website, photo URL.
    """
    from config import get_settings
    settings = get_settings()

    if not settings.google_places_api_key:
        raise HTTPException(status_code=503, detail="Google Places API not configured")

    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": _FIELDS,
        "key": settings.google_places_api_key,
    }

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        raise HTTPException(status_code=502, detail=f"Places API: {data.get('status')}")

    result = data.get("result", {})

    # Build a photo URL from the first available photo reference, if the store has any photos
    photo_url = None
    photos = result.get("photos", [])
    if photos and settings.google_places_api_key:
        ref = photos[0].get("photo_reference", "")
        if ref:
            photo_url = (
                f"https://maps.googleapis.com/maps/api/place/photo"
                f"?maxwidth=400&photo_reference={ref}&key={settings.google_places_api_key}"
            )

    # Extract open_now flag and per-day text hours from the opening_hours block
    hours = result.get("opening_hours", {})
    open_now = hours.get("open_now")
    weekday_text = hours.get("weekday_text", [])  # ["Monday: 9:00 AM – 9:00 PM", ...]

    # Flag permanently closed stores so the map popup can show a clear warning instead of hours
    status = result.get("business_status", "OPERATIONAL")
    is_closed_permanently = status == "CLOSED_PERMANENTLY"

    return {
        "name": result.get("name", ""),
        "address": result.get("formatted_address", ""),
        "phone": result.get("formatted_phone_number", ""),
        "website": result.get("website", ""),
        "rating": result.get("rating"),
        "review_count": result.get("user_ratings_total"),
        "price_level": result.get("price_level"),
        "open_now": open_now,
        "weekday_hours": weekday_text,
        "photo_url": photo_url,
        "is_closed_permanently": is_closed_permanently,
        "maps_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
    }
