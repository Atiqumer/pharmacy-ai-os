from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import pandas as pd
import io
import math
from datetime import date
from app.database import get_db_connection
from app.services.auth import get_current_user

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/inventory", tags=["Inventory Management"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_ROWS = 5000
MAX_TEXT_LENGTH = 255


def _required_text(value, field_name: str, row_number: int) -> str:
    if pd.isna(value) or not str(value).strip():
        raise ValueError(f"Row {row_number}: '{field_name}' is required")
    result = str(value).strip()
    if len(result) > MAX_TEXT_LENGTH:
        raise ValueError(f"Row {row_number}: '{field_name}' is too long")
    return result


def _non_negative_number(value, field_name: str, row_number: int, integer=False):
    try:
        result = int(value) if integer else float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"Row {row_number}: '{field_name}' must be a number")
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Row {row_number}: '{field_name}' must be zero or greater")
    return result


@router.post("/upload-csv")
@limiter.limit("10/minute")
async def upload_inventory_csv(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a valid CSV file.",
        )

    try:
        conn = None
        cursor = None
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="The uploaded CSV is empty.")
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="CSV files are limited to 5 MB.")
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

        if df.empty:
            raise HTTPException(status_code=400, detail="The CSV contains no inventory rows.")
        if len(df.index) > MAX_UPLOAD_ROWS:
            raise HTTPException(status_code=413, detail="A maximum of 5,000 rows can be imported at once.")

        validated_rows = []
        for index, row in df.iterrows():
            row_number = index + 2
            try:
                expiry = date.fromisoformat(_required_text(row["expiry_date"], "expiry_date", row_number))
            except ValueError as exc:
                if str(exc).startswith("Row"):
                    raise
                raise ValueError(f"Row {row_number}: 'expiry_date' must use YYYY-MM-DD format")

            validated_rows.append({
                "product_name": _required_text(row["product_name"], "product_name", row_number),
                "generic_name": _required_text(row["generic_name"], "generic_name", row_number),
                "category": _required_text(row["category"], "category", row_number),
                "batch_number": _required_text(row["batch_number"], "batch_number", row_number),
                "quantity": _non_negative_number(row["quantity"], "quantity", row_number, integer=True),
                "cost_price": _non_negative_number(row["cost_price"], "cost_price", row_number),
                "retail_price": _non_negative_number(row["retail_price"], "retail_price", row_number),
                "min_stock_level": _non_negative_number(row["min_stock_level"], "min_stock_level", row_number, integer=True),
                "expiry_date": expiry,
            })

        conn = get_db_connection()
        cursor = conn.cursor()
        owner_id = user["user_id"]
        records_imported = 0

        cursor.execute(
            """INSERT INTO "Supplier" (id, name, "ownerId")
               VALUES (gen_random_uuid(), 'Default Supplier', %s)
               ON CONFLICT ("ownerId", name) DO UPDATE SET name = EXCLUDED.name
               RETURNING id;""",
            (owner_id,),
        )
        supplier_id = cursor.fetchone()["id"]

        for row in validated_rows:
            cursor.execute(
                """INSERT INTO "Product" (id, name, "genericName", category, "minStockLevel", "ownerId")
                   VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
                   ON CONFLICT ("ownerId", name) DO UPDATE SET
                     "genericName" = EXCLUDED."genericName",
                     category = EXCLUDED.category,
                     "minStockLevel" = EXCLUDED."minStockLevel"
                   RETURNING id;""",
                (row["product_name"], row["generic_name"], row["category"], row["min_stock_level"], owner_id),
            )
            product_id = cursor.fetchone()["id"]

            cursor.execute(
                """INSERT INTO "Batch" (id, "batchNumber", "productId", "supplierId", quantity, "costPrice", "retailPrice", "expiryDate", "ownerId")
                   VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT ("ownerId", "productId", "batchNumber") DO UPDATE SET
                     "supplierId" = EXCLUDED."supplierId",
                     quantity = EXCLUDED.quantity,
                     "costPrice" = EXCLUDED."costPrice",
                     "retailPrice" = EXCLUDED."retailPrice",
                     "expiryDate" = EXCLUDED."expiryDate";""",
                (row["batch_number"], product_id, supplier_id, row["quantity"],
                 row["cost_price"], row["retail_price"], row["expiry_date"], owner_id),
            )
            records_imported += 1

        conn.commit()
        return {"status": "success", "message": f"Successfully processed and stored {records_imported} batch items."}

    except HTTPException:
        raise
    except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        if "conn" in locals() and conn:
            conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        if cursor is not None and not cursor.closed:
            cursor.close()
        if conn is not None:
            conn.close()
