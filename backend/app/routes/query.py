from fastapi import APIRouter, HTTPException, Query
from app.services.query_service import execute_natural_query

router = APIRouter(prefix="/query", tags=["Conversational Search Engine"])

@router.get("/ask")
async def ask_database(q: str = Query(..., description="Your plain English business question")):
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter cannot be empty.")
        
    result = execute_natural_query(q)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["detail"])
    return result