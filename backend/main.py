from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings

settings = get_settings()

app = FastAPI(
    title="ShopSmart API",
    description="Product discovery and price intelligence backend",
    version="1.0.0"
)

# In production, lock CORS to the exact Vercel domain set in FRONTEND_URL env var.
# Falls back to "*" only if FRONTEND_URL is not configured yet.
if settings.app_env == "production":
    _origins = [settings.frontend_url] if settings.frontend_url else ["*"]
else:
    _origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
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
from routes import search, analyze, place, alerts
app.include_router(search.router, prefix="/api/v1")
app.include_router(analyze.router, prefix="/api/v1")
app.include_router(place.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
