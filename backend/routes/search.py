from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from services.search_pipeline import SearchPipeline

router = APIRouter()
pipeline = SearchPipeline()


@router.get("/search")
async def search_products(
    q: str = Query(..., description="Product search query", min_length=1),
    lat: Optional[float] = Query(None, description="User latitude"),
    lon: Optional[float] = Query(None, description="User longitude"),
    city: Optional[str] = Query(None, description="User city (if no GPS)"),
):
    """
    Main search endpoint.

    Called by the frontend when user searches for a product.
    Returns top picks + all results + local store map pins.

    Example: GET /api/v1/search?q=Sony+headphones&city=Austin
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        results = await pipeline.search(
            query=q.strip(),
            lat=lat,
            lon=lon,
            city=city,
        )
        return results
    except Exception as e:
        print(f"[Search Route] Error: {e}")
        raise HTTPException(status_code=500, detail="Search failed. Please try again.")
