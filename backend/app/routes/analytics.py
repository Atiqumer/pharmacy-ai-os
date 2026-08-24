from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.services.ai_service import generate_morning_briefing
from app.services.auth import get_current_user
from app.database import get_db_connection

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/analytics", tags=["AI Analytics & Insights"])


@router.get("/morning-briefing")
@limiter.limit("5/minute")
async def get_get_briefing(request: Request, user: dict = Depends(get_current_user)):
    result = generate_morning_briefing(user["user_id"])
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["detail"])
    return result


@router.get("/reorder-suggestions")
@limiter.limit("15/minute")
async def get_reorder_suggestions(request: Request, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """WITH stock AS (
                   SELECT p.id, p.name, p."genericName", p."minStockLevel",
                          COALESCE(SUM(b.quantity), 0) AS current_stock
                   FROM "Product" p
                   LEFT JOIN "Batch" b ON b."productId" = p.id AND b."ownerId" = %s
                   WHERE p."ownerId" = %s
                   GROUP BY p.id
               )
               SELECT s.id, s.name, s."genericName", s."minStockLevel", s.current_stock,
                      GREATEST((s."minStockLevel" * 2) - s.current_stock, 1) AS suggested_quantity,
                      latest."costPrice", latest.supplier_name
               FROM stock s
               LEFT JOIN LATERAL (
                   SELECT b."costPrice", sup.name AS supplier_name
                   FROM "Batch" b
                   LEFT JOIN "Supplier" sup ON sup.id = b."supplierId" AND sup."ownerId" = %s
                   WHERE b."productId" = s.id AND b."ownerId" = %s
                   ORDER BY b.created_at DESC LIMIT 1
               ) latest ON TRUE
               WHERE s."minStockLevel" > 0 AND s.current_stock <= s."minStockLevel"
               ORDER BY (s."minStockLevel" - s.current_stock) DESC, s.name;""",
            (user["user_id"], user["user_id"], user["user_id"], user["user_id"]),
        )
        rows = cursor.fetchall()
        return {"suggestions": [{
            "product_id": str(row["id"]), "product_name": row["name"],
            "generic_name": row["genericName"], "current_stock": row["current_stock"],
            "min_stock_level": row["minStockLevel"], "suggested_quantity": row["suggested_quantity"],
            "last_cost_price": float(row["costPrice"]) if row["costPrice"] is not None else None,
            "last_supplier": row["supplier_name"],
        } for row in rows]}
    finally:
        cursor.close()
        conn.close()
