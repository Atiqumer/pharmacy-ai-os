from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
import pandas as pd
import io
import math
from datetime import date
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator
from app.database import get_db_connection
from app.utils.datetime import utc_isoformat
from app.services.auth import get_current_user

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/inventory", tags=["Inventory Management"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_ROWS = 5000
MAX_TEXT_LENGTH = 255


class ManualInventoryItem(BaseModel):
    product_name: str = Field(min_length=1, max_length=255)
    generic_name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    min_stock_level: int = Field(default=10, ge=0)
    batch_number: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=0)
    cost_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    retail_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    expiry_date: date
    supplier_name: str = Field(default="Default Supplier", min_length=1, max_length=255)


class StockAdjustment(BaseModel):
    quantity_change: int
    reason: Literal["purchase", "sale", "return", "damage", "expired", "correction", "other"]
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("quantity_change")
    @classmethod
    def quantity_change_must_not_be_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("quantity_change must not be zero")
        return value


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    generic_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    min_stock_level: Optional[int] = Field(default=None, ge=0)
    sku: Optional[str] = Field(default=None, max_length=100)
    barcode: Optional[str] = Field(default=None, max_length=100)
    manufacturer: Optional[str] = Field(default=None, max_length=255)
    strength: Optional[str] = Field(default=None, max_length=100)
    dosage_form: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one product field must be supplied")
        return self


class BatchUpdate(BaseModel):
    batch_number: Optional[str] = Field(default=None, min_length=1, max_length=100)
    supplier_id: Optional[UUID] = None
    cost_price: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    retail_price: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    expiry_date: Optional[date] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one batch field must be supplied")
        return self


@router.post("/items", status_code=201)
@limiter.limit("30/minute")
async def create_inventory_item(
    request: Request,
    item: ManualInventoryItem,
    user: dict = Depends(get_current_user),
):
    owner_id = user["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO "Product" (id, name, "genericName", category, "minStockLevel", "ownerId")
               VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
               ON CONFLICT ("ownerId", name) DO UPDATE SET
                 "genericName" = EXCLUDED."genericName",
                 category = EXCLUDED.category,
                 "minStockLevel" = EXCLUDED."minStockLevel",
                 is_active = TRUE,
                 updated_at = NOW()
               RETURNING id;""",
            (
                item.product_name.strip(),
                item.generic_name.strip(),
                item.category.strip(),
                item.min_stock_level,
                owner_id,
            ),
        )
        product_id = cursor.fetchone()["id"]

        cursor.execute(
            """INSERT INTO "Supplier" (id, name, "ownerId")
               VALUES (gen_random_uuid(), %s, %s)
               ON CONFLICT ("ownerId", name) DO UPDATE SET name = EXCLUDED.name
               RETURNING id;""",
            (item.supplier_name.strip(), owner_id),
        )
        supplier_id = cursor.fetchone()["id"]

        cursor.execute(
            """INSERT INTO "Batch" (
                   id, "batchNumber", "productId", "supplierId", quantity,
                   "costPrice", "retailPrice", "expiryDate", "ownerId"
               ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT ("ownerId", "productId", "batchNumber") DO NOTHING
               RETURNING id;""",
            (
                item.batch_number.strip(), product_id, supplier_id, item.quantity,
                item.cost_price, item.retail_price, item.expiry_date, owner_id,
            ),
        )
        batch = cursor.fetchone()
        if not batch:
            raise HTTPException(status_code=409, detail="This batch already exists for the product")
        batch_id = batch["id"]

        if item.quantity > 0:
            cursor.execute(
                """INSERT INTO "StockMovement" (
                       id, "batchId", "productId", "ownerId", "createdBy",
                       "quantityChange", "quantityBefore", "quantityAfter", reason, note
                   ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, 0, %s, 'opening', %s);""",
                (
                    batch_id, product_id, owner_id, owner_id, item.quantity,
                    item.quantity, "Manual opening stock",
                ),
            )

        conn.commit()
        return {
            "message": "Inventory batch created",
            "batch_id": str(batch_id),
            "product_id": str(product_id),
            "quantity": item.quantity,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Inventory batch could not be created") from exc
    finally:
        cursor.close()
        conn.close()


@router.post("/items/{batch_id}/adjust")
@limiter.limit("30/minute")
async def adjust_batch_stock(
    request: Request,
    batch_id: UUID,
    adjustment: StockAdjustment,
    user: dict = Depends(get_current_user),
):
    owner_id = user["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT id, "productId", quantity
               FROM "Batch"
               WHERE id = %s AND "ownerId" = %s
               FOR UPDATE;""",
            (str(batch_id), owner_id),
        )
        batch = cursor.fetchone()
        if not batch:
            raise HTTPException(status_code=404, detail="Inventory batch not found")

        quantity_before = batch["quantity"]
        quantity_after = quantity_before + adjustment.quantity_change
        if quantity_after < 0:
            raise HTTPException(
                status_code=409,
                detail=f"Adjustment would make stock negative. Available quantity: {quantity_before}",
            )

        cursor.execute(
            'UPDATE "Batch" SET quantity = %s WHERE id = %s AND "ownerId" = %s;',
            (quantity_after, str(batch_id), owner_id),
        )
        cursor.execute(
            """INSERT INTO "StockMovement" (
                   id, "batchId", "productId", "ownerId", "createdBy",
                   "quantityChange", "quantityBefore", "quantityAfter", reason, note
               ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id, created_at;""",
            (
                str(batch_id), batch["productId"], owner_id, owner_id,
                adjustment.quantity_change, quantity_before, quantity_after,
                adjustment.reason, adjustment.note.strip() if adjustment.note else None,
            ),
        )
        movement = cursor.fetchone()
        conn.commit()
        return {
            "message": "Stock adjusted",
            "movement_id": str(movement["id"]),
            "quantity_before": quantity_before,
            "quantity_change": adjustment.quantity_change,
            "quantity_after": quantity_after,
            "reason": adjustment.reason,
            "created_at": utc_isoformat(movement["created_at"]),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Stock could not be adjusted") from exc
    finally:
        cursor.close()
        conn.close()


@router.patch("/products/{product_id}")
@limiter.limit("30/minute")
async def update_product(
    request: Request,
    product_id: UUID,
    update: ProductUpdate,
    user: dict = Depends(get_current_user),
):
    owner_id = user["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, is_active FROM "Product" WHERE id = %s AND "ownerId" = %s FOR UPDATE;',
            (str(product_id), owner_id),
        )
        product = cursor.fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        if update.is_active is False:
            cursor.execute(
                'SELECT COALESCE(SUM(quantity), 0) AS stock FROM "Batch" WHERE "productId" = %s AND "ownerId" = %s;',
                (str(product_id), owner_id),
            )
            if cursor.fetchone()["stock"] > 0:
                raise HTTPException(status_code=409, detail="Reduce this product's stock to zero before archiving it")
            cursor.execute(
                """SELECT 1 FROM "PurchaseOrderItem" poi
                   JOIN "PurchaseOrder" po ON po.id = poi."purchaseOrderId"
                   WHERE poi."productId" = %s AND po."ownerId" = %s
                     AND po.status IN ('draft','ordered','partially_received') LIMIT 1;""",
                (str(product_id), owner_id),
            )
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail="Cancel or complete open purchase orders before archiving this product")

        fields = {
            "name": update.name.strip() if update.name is not None else None,
            '"genericName"': update.generic_name.strip() if update.generic_name is not None else None,
            "category": update.category.strip() if update.category is not None else None,
            '"minStockLevel"': update.min_stock_level,
            "sku": update.sku.strip() or None if update.sku is not None else None,
            "barcode": update.barcode.strip() or None if update.barcode is not None else None,
            "manufacturer": update.manufacturer.strip() or None if update.manufacturer is not None else None,
            "strength": update.strength.strip() or None if update.strength is not None else None,
            "dosage_form": update.dosage_form.strip() or None if update.dosage_form is not None else None,
            "is_active": update.is_active,
        }
        requested = {
            "name": "name", "generic_name": '"genericName"', "category": "category",
            "min_stock_level": '"minStockLevel"', "sku": "sku", "barcode": "barcode",
            "manufacturer": "manufacturer", "strength": "strength",
            "dosage_form": "dosage_form", "is_active": "is_active",
        }
        columns = [requested[name] for name in update.model_fields_set]
        values = [fields[column] for column in columns]
        assignments = ", ".join(f"{column} = %s" for column in columns)
        cursor.execute(
            f'''UPDATE "Product" SET {assignments}, updated_at = NOW()
                WHERE id = %s AND "ownerId" = %s
                RETURNING id, name, "genericName", category, "minStockLevel", sku,
                          barcode, manufacturer, strength, dosage_form, is_active, updated_at;''',
            (*values, str(product_id), owner_id),
        )
        row = cursor.fetchone()
        conn.commit()
        return {
            "id": str(row["id"]), "name": row["name"], "generic_name": row["genericName"],
            "category": row["category"], "min_stock_level": row["minStockLevel"],
            "sku": row["sku"], "barcode": row["barcode"], "manufacturer": row["manufacturer"],
            "strength": row["strength"], "dosage_form": row["dosage_form"],
            "is_active": row["is_active"], "updated_at": utc_isoformat(row["updated_at"]),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        if getattr(exc, "pgcode", None) == "23505":
            raise HTTPException(status_code=409, detail="Product name, SKU, or barcode already exists") from exc
        raise HTTPException(status_code=500, detail="Product could not be updated") from exc
    finally:
        cursor.close()
        conn.close()


@router.patch("/items/{batch_id}")
@limiter.limit("30/minute")
async def update_batch(
    request: Request,
    batch_id: UUID,
    update: BatchUpdate,
    user: dict = Depends(get_current_user),
):
    owner_id = user["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, quantity FROM "Batch" WHERE id = %s AND "ownerId" = %s FOR UPDATE;',
            (str(batch_id), owner_id),
        )
        batch = cursor.fetchone()
        if not batch:
            raise HTTPException(status_code=404, detail="Inventory batch not found")
        if update.is_active is False and batch["quantity"] > 0:
            raise HTTPException(status_code=409, detail="Reduce this batch's stock to zero before archiving it")
        if "supplier_id" in update.model_fields_set and update.supplier_id is not None:
            cursor.execute(
                'SELECT id FROM "Supplier" WHERE id = %s AND "ownerId" = %s AND is_active = TRUE;',
                (str(update.supplier_id), owner_id),
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Active supplier not found")

        values_by_field = {
            "batch_number": update.batch_number.strip() if update.batch_number is not None else None,
            "supplier_id": str(update.supplier_id) if update.supplier_id else None,
            "cost_price": update.cost_price, "retail_price": update.retail_price,
            "expiry_date": update.expiry_date, "is_active": update.is_active,
        }
        columns = {
            "batch_number": '"batchNumber"', "supplier_id": '"supplierId"',
            "cost_price": '"costPrice"', "retail_price": '"retailPrice"',
            "expiry_date": '"expiryDate"', "is_active": "is_active",
        }
        requested = list(update.model_fields_set)
        assignments = ", ".join(f"{columns[name]} = %s" for name in requested)
        cursor.execute(
            f'''UPDATE "Batch" SET {assignments}, updated_at = NOW()
                WHERE id = %s AND "ownerId" = %s
                RETURNING id, "batchNumber", "supplierId", "costPrice", "retailPrice",
                          "expiryDate", quantity, is_active, updated_at;''',
            (*(values_by_field[name] for name in requested), str(batch_id), owner_id),
        )
        row = cursor.fetchone()
        conn.commit()
        return {
            "id": str(row["id"]), "batch_number": row["batchNumber"],
            "supplier_id": str(row["supplierId"]) if row["supplierId"] else None,
            "cost_price": float(row["costPrice"]), "retail_price": float(row["retailPrice"]),
            "expiry_date": str(row["expiryDate"]), "quantity": row["quantity"],
            "is_active": row["is_active"], "updated_at": utc_isoformat(row["updated_at"]),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        if getattr(exc, "pgcode", None) == "23505":
            raise HTTPException(status_code=409, detail="This batch number already exists for the product") from exc
        raise HTTPException(status_code=500, detail="Batch could not be updated") from exc
    finally:
        cursor.close()
        conn.close()


@router.get("/movements")
@limiter.limit("30/minute")
async def list_stock_movements(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    batch_id: Optional[UUID] = None,
    reason: Optional[Literal["opening", "purchase", "sale", "return", "damage", "expired", "correction", "other"]] = None,
    user: dict = Depends(get_current_user),
):
    conditions = ['m."ownerId" = %s']
    params = [user["user_id"]]
    if batch_id:
        conditions.append('m."batchId" = %s')
        params.append(str(batch_id))
    if reason:
        conditions.append('m.reason = %s')
        params.append(reason)
    params.extend([limit, (page - 1) * limit])

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""SELECT
                    m.id, m."batchId", p.name, b."batchNumber",
                    m."quantityChange", m."quantityBefore", m."quantityAfter",
                    m.reason, m.note, u.full_name, m.created_at,
                    COUNT(*) OVER() AS total_count
                FROM "StockMovement" m
                JOIN "Batch" b ON b.id = m."batchId" AND b."ownerId" = m."ownerId"
                JOIN "Product" p ON p.id = m."productId" AND p."ownerId" = m."ownerId"
                JOIN "User" u ON u.id = m."createdBy"
                WHERE {' AND '.join(conditions)}
                ORDER BY m.created_at DESC
                LIMIT %s OFFSET %s;""",
            tuple(params),
        )
        rows = cursor.fetchall()
        return {
            "movements": [
                {
                    "id": str(row["id"]),
                    "batch_id": str(row["batchId"]),
                    "product_name": row["name"],
                    "batch_number": row["batchNumber"],
                    "quantity_change": row["quantityChange"],
                    "quantity_before": row["quantityBefore"],
                    "quantity_after": row["quantityAfter"],
                    "reason": row["reason"],
                    "note": row["note"],
                    "created_by": row["full_name"],
                    "created_at": utc_isoformat(row["created_at"]),
                }
                for row in rows
            ],
            "total": rows[0]["total_count"] if rows else 0,
            "page": page,
            "limit": limit,
        }
    finally:
        cursor.close()
        conn.close()


@router.get("/summary")
@limiter.limit("30/minute")
async def get_inventory_summary(
    request: Request,
    user: dict = Depends(get_current_user),
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        owner_id = user["user_id"]
        cursor.execute(
            """
            WITH product_stock AS (
                SELECT p.id, p."minStockLevel", COALESCE(SUM(b.quantity), 0) AS stock
                FROM "Product" p
                LEFT JOIN "Batch" b
                  ON b."productId" = p.id AND b."ownerId" = %s AND b.is_active = TRUE
                WHERE p."ownerId" = %s AND p.is_active = TRUE
                GROUP BY p.id, p."minStockLevel"
            ), batch_metrics AS (
                SELECT
                    COALESCE(SUM(quantity), 0) AS total_units,
                    COALESCE(SUM(quantity * "costPrice"), 0) AS cost_value,
                    COALESCE(SUM(quantity * "retailPrice"), 0) AS retail_value,
                    COUNT(*) FILTER (
                        WHERE "expiryDate" >= CURRENT_DATE
                          AND "expiryDate" <= CURRENT_DATE + INTERVAL '90 days'
                    ) AS expiring_batches,
                    COUNT(*) FILTER (WHERE "expiryDate" < CURRENT_DATE) AS expired_batches
                FROM "Batch"
                WHERE "ownerId" = %s AND is_active = TRUE
            )
            SELECT
                (SELECT COUNT(*) FROM product_stock) AS total_products,
                (SELECT COUNT(*) FROM product_stock WHERE stock <= "minStockLevel") AS low_stock_products,
                total_units,
                cost_value,
                retail_value,
                expiring_batches,
                expired_batches
            FROM batch_metrics;
            """,
            (owner_id, owner_id, owner_id),
        )
        row = cursor.fetchone()
        return {
            "total_products": row["total_products"],
            "total_units": row["total_units"],
            "low_stock_products": row["low_stock_products"],
            "expiring_batches": row["expiring_batches"],
            "expired_batches": row["expired_batches"],
            "cost_value": float(row["cost_value"]),
            "retail_value": float(row["retail_value"]),
            "potential_margin": float(row["retail_value"] - row["cost_value"]),
        }
    finally:
        cursor.close()
        conn.close()


@router.get("/items")
@limiter.limit("30/minute")
async def list_inventory_items(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    search: str = Query("", max_length=100),
    stock_status: str = Query("all", pattern="^(all|low_stock|in_stock)$"),
    expiry_status: str = Query("all", pattern="^(all|expiring|expired|valid)$"),
    include_inactive: bool = False,
    user: dict = Depends(get_current_user),
):
    owner_id = user["user_id"]
    conditions = []
    params = [owner_id, owner_id]

    if not include_inactive:
        conditions.append("product_is_active = TRUE AND batch_is_active = TRUE")

    if search.strip():
        conditions.append(
            '(name ILIKE %s OR "genericName" ILIKE %s OR category ILIKE %s OR "batchNumber" ILIKE %s)'
        )
        term = f"%{search.strip()}%"
        params.extend([term, term, term, term])
    if stock_status == "low_stock":
        conditions.append('total_stock <= "minStockLevel"')
    elif stock_status == "in_stock":
        conditions.append('total_stock > "minStockLevel"')
    if expiry_status == "expiring":
        conditions.append('"expiryDate" >= CURRENT_DATE AND "expiryDate" <= CURRENT_DATE + INTERVAL \'90 days\'')
    elif expiry_status == "expired":
        conditions.append('"expiryDate" < CURRENT_DATE')
    elif expiry_status == "valid":
        conditions.append('"expiryDate" > CURRENT_DATE + INTERVAL \'90 days\'')

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * limit
    params.extend([limit, offset])

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
            WITH inventory AS (
                SELECT
                    b.id AS batch_id,
                    p.id AS product_id,
                    p.name,
                    p."genericName",
                    p.category,
                    p."minStockLevel",
                    p.sku,
                    p.barcode,
                    p.manufacturer,
                    p.strength,
                    p.dosage_form,
                    p.is_active AS product_is_active,
                    b."batchNumber",
                    b.quantity,
                    b."costPrice",
                    b."retailPrice",
                    b."expiryDate",
                    b."supplierId",
                    b.is_active AS batch_is_active,
                    SUM(b.quantity) OVER (PARTITION BY p.id) AS total_stock
                FROM "Batch" b
                JOIN "Product" p ON p.id = b."productId" AND p."ownerId" = %s
                WHERE b."ownerId" = %s
            )
            SELECT *, COUNT(*) OVER() AS total_count
            FROM inventory
            {where_clause}
            ORDER BY "expiryDate" ASC, name ASC
            LIMIT %s OFFSET %s;
            """,
            tuple(params),
        )
        rows = cursor.fetchall()
        total = rows[0]["total_count"] if rows else 0
        return {
            "items": [
                {
                    "batch_id": str(row["batch_id"]),
                    "product_id": str(row["product_id"]),
                    "name": row["name"],
                    "generic_name": row["genericName"],
                    "category": row["category"],
                    "batch_number": row["batchNumber"],
                    "quantity": row["quantity"],
                    "total_stock": row["total_stock"],
                    "min_stock_level": row["minStockLevel"],
                    "sku": row["sku"],
                    "barcode": row["barcode"],
                    "manufacturer": row["manufacturer"],
                    "strength": row["strength"],
                    "dosage_form": row["dosage_form"],
                    "cost_price": float(row["costPrice"]),
                    "retail_price": float(row["retailPrice"]),
                    "expiry_date": str(row["expiryDate"]),
                    "supplier_id": str(row["supplierId"]) if row["supplierId"] else None,
                    "product_is_active": row["product_is_active"],
                    "batch_is_active": row["batch_is_active"],
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "limit": limit,
        }
    finally:
        cursor.close()
        conn.close()


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
        movements_recorded = 0
        import_name = file.filename.replace("\\", "/").rsplit("/", 1)[-1][:200]

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
                     "minStockLevel" = EXCLUDED."minStockLevel",
                     is_active = TRUE,
                     updated_at = NOW()
                   RETURNING id;""",
                (row["product_name"], row["generic_name"], row["category"], row["min_stock_level"], owner_id),
            )
            product_id = cursor.fetchone()["id"]

            cursor.execute(
                """SELECT id, quantity
                   FROM "Batch"
                   WHERE "ownerId" = %s AND "productId" = %s AND "batchNumber" = %s
                   FOR UPDATE;""",
                (owner_id, product_id, row["batch_number"]),
            )
            existing_batch = cursor.fetchone()
            quantity_before = existing_batch["quantity"] if existing_batch else 0

            cursor.execute(
                """INSERT INTO "Batch" (id, "batchNumber", "productId", "supplierId", quantity, "costPrice", "retailPrice", "expiryDate", "ownerId")
                   VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT ("ownerId", "productId", "batchNumber") DO UPDATE SET
                     "supplierId" = EXCLUDED."supplierId",
                     quantity = EXCLUDED.quantity,
                     "costPrice" = EXCLUDED."costPrice",
                     "retailPrice" = EXCLUDED."retailPrice",
                     "expiryDate" = EXCLUDED."expiryDate"
                   RETURNING id;""",
                (row["batch_number"], product_id, supplier_id, row["quantity"],
                 row["cost_price"], row["retail_price"], row["expiry_date"], owner_id),
            )
            batch_id = cursor.fetchone()["id"]
            quantity_change = row["quantity"] - quantity_before
            if quantity_change:
                cursor.execute(
                    """INSERT INTO "StockMovement" (
                           id, "batchId", "productId", "ownerId", "createdBy",
                           "quantityChange", "quantityBefore", "quantityAfter", reason, note
                       ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s);""",
                    (
                        batch_id, product_id, owner_id, owner_id, quantity_change,
                        quantity_before, row["quantity"],
                        "correction" if existing_batch else "opening",
                        f"CSV import from {import_name}",
                    ),
                )
                movements_recorded += 1
            records_imported += 1

        conn.commit()
        return {
            "status": "success",
            "message": f"Successfully processed and stored {records_imported} batch items.",
            "movements_recorded": movements_recorded,
        }

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
