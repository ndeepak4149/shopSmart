from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings

settings = get_settings()

app = FastAPI(
    title="ShopSmart API",
    description="Product discovery and price intelligence backend",
    version="1.0.0"
)

# Allow the frontend (Next.js on port 3000) to talk to this backend
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


# ── Routes ────────────────────────────────────────────────────────
from routes import search
app.include_router(search.router, prefix="/api/v1")
