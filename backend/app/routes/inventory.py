from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import pandas as pd
import io
from app.database import get_db_connection
from app.services.auth import get_current_user

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/inventory", tags=["Inventory Management"])


@router.post("/upload-csv")
@limiter.limit("10/minute")
async def upload_inventory_csv(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a valid CSV file.",
        )

    try:
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
        df.columns = [c.strip() for c in df.columns]

        required_columns = [
            "product_name", "generic_name", "category", "batch_number",
            "quantity", "cost_price", "retail_price", "expiry_date",
        ]
        for col in required_columns:
            if col not in df.columns:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required data column: '{col}'",
                )

        if "min_stock_level" not in df.columns:
            df["min_stock_level"] = 10

        conn = get_db_connection()
        cursor = conn.cursor()
        owner_id = user["user_id"]
        records_imported = 0

        for _, row in df.iterrows():
            cursor.execute(
                'SELECT id FROM "Product" WHERE name = %s AND "ownerId" = %s LIMIT 1;',
                (row["product_name"], owner_id),
            )
            product = cursor.fetchone()

            if product:
                product_id = product["id"]
            else:
                cursor.execute(
                    """INSERT INTO "Product" (id, name, "genericName", category, "minStockLevel", "ownerId")
                       VALUES (gen_random_uuid(), %s, %s, %s, %s, %s) RETURNING id;""",
                    (row["product_name"], row["generic_name"], row["category"], int(row["min_stock_level"]), owner_id),
                )
                product_id = cursor.fetchone()["id"]

            cursor.execute('SELECT id FROM "Supplier" WHERE "ownerId" = %s LIMIT 1;', (owner_id,))
            supplier = cursor.fetchone()
            if supplier:
                supplier_id = supplier["id"]
            else:
                cursor.execute(
                    """INSERT INTO "Supplier" (id, name, "ownerId")
                       VALUES (gen_random_uuid(), 'Default Supplier', %s) RETURNING id;""",
                    (owner_id,),
                )
                supplier_id = cursor.fetchone()["id"]

            cursor.execute(
                """INSERT INTO "Batch" (id, "batchNumber", "productId", "supplierId", quantity, "costPrice", "retailPrice", "expiryDate", "ownerId")
                   VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, TO_DATE(%s, 'YYYY-MM-DD'), %s);""",
                (str(row["batch_number"]), product_id, supplier_id, int(row["quantity"]),
                 float(row["cost_price"]), float(row["retail_price"]), str(row["expiry_date"]), owner_id),
            )
            records_imported += 1

        conn.commit()
        cursor.close()
        conn.close()

        return {"status": "success", "message": f"Successfully processed and stored {records_imported} batch items."}

    except HTTPException:
        raise
    except Exception as e:
        if "conn" in locals() and conn:
            conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
