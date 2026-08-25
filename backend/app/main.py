import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.routes import inventory, query, analytics, auth, admin, suppliers, purchasing, sales, reports, workspace
from app.middleware.logging import log_requests

logger = logging.getLogger("rxos")

limiter = Limiter(key_func=get_remote_address)


app = FastAPI(
    title="AI-Powered Pharmacy OS Engine",
    description="The intelligent data automation layer for independent medical stores.",
    version="2.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    response = await log_requests(request, call_next)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), payment=()"
    return response


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(inventory.router)
app.include_router(suppliers.router)
app.include_router(purchasing.router)
app.include_router(sales.router)
app.include_router(reports.router)
app.include_router(workspace.router)
app.include_router(analytics.router)
app.include_router(query.router)


@app.get("/")
@limiter.limit("30/minute")
async def read_root(request: Request):
    return {
        "status": "online",
        "system": "AI Pharmacy Operating System Backend Engine",
        "version": "2.0.0",
    }


@app.get("/health/live", include_in_schema=False)
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready", include_in_schema=False)
async def health_ready():
    from app.database import get_db_connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version_num FROM alembic_version LIMIT 1;")
        migration = cursor.fetchone()
        return {"status": "ready", "migration": migration["version_num"]}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is not ready") from exc
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()
