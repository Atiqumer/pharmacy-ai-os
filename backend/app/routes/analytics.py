from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.services.ai_service import generate_morning_briefing
from app.services.auth import get_current_user

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/analytics", tags=["AI Analytics & Insights"])


@router.get("/morning-briefing")
@limiter.limit("5/minute")
async def get_get_briefing(request: Request, user: dict = Depends(get_current_user)):
    result = generate_morning_briefing(user["user_id"])
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["detail"])
    return result
