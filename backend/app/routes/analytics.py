from fastapi import APIRouter, HTTPException
from app.services.ai_service import generate_morning_briefing

router = APIRouter(prefix="/analytics", tags=["AI Analytics & Insights"])

@router.get("/morning-briefing")
async def get_get_briefing():
    result = generate_morning_briefing()
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["detail"])
    return result