import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.routes import inventory, query, analytics, auth, admin, suppliers, purchasing
from app.middleware.logging import log_requests
from app.database import init_db

logger = logging.getLogger("rxos")

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
        logger.warning(f"DB init skipped: {e}")
    yield


app = FastAPI(
    title="AI-Powered Pharmacy OS Engine",
    description="The intelligent data automation layer for independent medical stores.",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    return await log_requests(request, call_next)


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(inventory.router)
app.include_router(suppliers.router)
app.include_router(purchasing.router)
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
