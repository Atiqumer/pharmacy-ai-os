from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.services.query_service import execute_natural_query
from app.services.auth import get_current_user

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/query", tags=["Conversational Search Engine"])


@router.get("/ask")
@limiter.limit("15/minute")
async def ask_database(
    request: Request,
    q: str = Query(..., description="Your plain English business question"),
    user: dict = Depends(get_current_user),
):
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter cannot be empty.")

    result = execute_natural_query(q, user["user_id"])
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["detail"])
    return result
