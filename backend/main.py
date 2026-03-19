from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings

settings = get_settings()

app = FastAPI(
    title="ShopSmart API",
    description="Product discovery and price intelligence backend",
    version="1.0.0"
)

# Allow the Next.js dev server on port 3000 to make cross-origin requests to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ShopSmart API is running"}


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.app_env}


# Register route modules — each adds its own endpoints under /api/v1
from routes import search, analyze, place
app.include_router(search.router, prefix="/api/v1")
app.include_router(analyze.router, prefix="/api/v1")
app.include_router(place.router, prefix="/api/v1")
