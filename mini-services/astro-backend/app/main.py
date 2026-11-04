import app.core.ssl_fix  # noqa: F401  repairs certifi bundle BEFORE yfinance/curl_cffi load
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes, routes_quant, routes_models, routes_cycles, routes_jataka, routes_strategy, routes_panchang, routes_astrologers
from app.core.config import settings

app = FastAPI(
    title="AstroTrader API",
    description="Technical exploration of planetary position calculations and market data correlations",
    version="1.5.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ASTRO_CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(routes.router, prefix="/api/v1")
# v1.3 feature routers — one per area so they evolve independently
for _r in (routes_quant, routes_models, routes_cycles, routes_jataka, routes_strategy,
           routes_panchang, routes_astrologers):
    app.include_router(_r.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "AstroTrader API - Technical Exploration Only",
        "disclaimer": "This API is for educational purposes only. Not financial advice.",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}