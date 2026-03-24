from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from services.search_pipeline import SearchPipeline

router = APIRouter()
_pipeline = None  # SearchPipeline singleton — created on first request to avoid startup cost

def get_pipeline():
    # Lazy-initialize the pipeline so the ML model only trains once per process
    global _pipeline
    if _pipeline is None:
        _pipeline = SearchPipeline()
    return _pipeline


@router.get("/search")
async def search_products(
    q: str = Query(..., description="Product search query", min_length=1),
    lat: Optional[float] = Query(None, description="User latitude"),
    lon: Optional[float] = Query(None, description="User longitude"),
    city: Optional[str] = Query(None, description="User city (if no GPS)"),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        results = await get_pipeline().search(
            query=q.strip(),
            lat=lat,
            lon=lon,
            city=city,
        )
        return results
    except Exception as e:
        import traceback
        print(f"[Search Route] Error: {e}")
        print(f"[Search Route] Traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
