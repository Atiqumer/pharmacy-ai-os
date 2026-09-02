from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db_connection
from app.utils.datetime import utc_isoformat
from app.services.auth import get_current_user

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/sales", tags=["Sales"])
MONEY = Decimal("0.01")


class SaleLineCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, le=100000)
    unit_price: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class SaleCreate(BaseModel):
    items: list[SaleLineCreate] = Field(min_length=1, max_length=100)
    discount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def products_must_be_unique(self):
        product_ids = [line.product_id for line in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Each product can appear only once in a sale")
        return self


class ReturnLineCreate(BaseModel):
    sale_item_id: UUID
    quantity: int = Field(gt=0, le=100000)


class SalesReturnCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    items: list[ReturnLineCreate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def sale_items_must_be_unique(self):
        ids = [line.sale_item_id for line in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Each sale item can appear only once in a return")
        return self


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


@router.post("", status_code=201)
@limiter.limit("60/minute")
async def create_sale(
    request: Request,
    sale: SaleCreate,
    user: dict = Depends(get_current_user),
):
    owner_id = user["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        allocations = []
        subtotal = Decimal("0")

        for line in sale.items:
            cursor.execute(
                'SELECT id, name FROM "Product" WHERE id = %s AND "ownerId" = %s AND is_active = TRUE;',
                (str(line.product_id), owner_id),
            )
            product = cursor.fetchone()
            if not product:
                raise HTTPException(status_code=404, detail="Active product not found")

            cursor.execute(
                """SELECT id, quantity, "retailPrice", "costPrice", "expiryDate"
                   FROM "Batch"
                   WHERE "productId" = %s AND "ownerId" = %s AND is_active = TRUE
                     AND quantity > 0 AND "expiryDate" >= CURRENT_DATE
                   ORDER BY "expiryDate" ASC, created_at ASC
                   FOR UPDATE;""",
                (str(line.product_id), owner_id),
            )
            batches = cursor.fetchall()
            available = sum(batch["quantity"] for batch in batches)
            if available < line.quantity:
                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient non-expired stock for {product['name']}. Available: {available}",
                )

            remaining = line.quantity
            for batch in batches:
                if remaining == 0:
                    break
                allocated = min(remaining, batch["quantity"])
                unit_price = line.unit_price if line.unit_price is not None else batch["retailPrice"]
                line_total = _money(unit_price * allocated)
                allocations.append({
                    "product_id": line.product_id,
                    "product_name": product["name"],
                    "batch": batch,
                    "quantity": allocated,
                    "unit_price": unit_price,
                    "line_total": line_total,
                })
                subtotal += line_total
                remaining -= allocated

        subtotal = _money(subtotal)
        if sale.discount > subtotal:
            raise HTTPException(status_code=400, detail="Discount cannot exceed the sale subtotal")
        total = _money(subtotal - sale.discount)

        cursor.execute(
            """INSERT INTO "Sale" (
                   id, "saleNumber", "ownerId", "createdBy", subtotal, discount, total, notes
               ) VALUES (
                   gen_random_uuid(),
                   'SALE-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || UPPER(SUBSTRING(REPLACE(gen_random_uuid()::text, '-', ''), 1, 6)),
                   %s, %s, %s, %s, %s, %s
               ) RETURNING id, "saleNumber", status, created_at;""",
            (owner_id, owner_id, subtotal, sale.discount, total, sale.notes.strip() if sale.notes else None),
        )
        sale_row = cursor.fetchone()

        for allocation in allocations:
            batch = allocation["batch"]
            quantity_after = batch["quantity"] - allocation["quantity"]
            cursor.execute(
                'UPDATE "Batch" SET quantity = %s, updated_at = NOW() WHERE id = %s AND "ownerId" = %s;',
                (quantity_after, batch["id"], owner_id),
            )
            cursor.execute(
                """INSERT INTO "SaleItem" (
                       id, "saleId", "productId", "batchId", quantity,
                       "unitPrice", "costPrice", "lineTotal"
                   ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s);""",
                (
                    sale_row["id"], str(allocation["product_id"]), batch["id"],
                    allocation["quantity"], allocation["unit_price"], batch["costPrice"],
                    allocation["line_total"],
                ),
            )
            cursor.execute(
                """INSERT INTO "StockMovement" (
                       id, "batchId", "productId", "ownerId", "createdBy",
                       "quantityChange", "quantityBefore", "quantityAfter", reason, note
                   ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, 'sale', %s);""",
                (
                    batch["id"], str(allocation["product_id"]), owner_id, owner_id,
                    -allocation["quantity"], batch["quantity"], quantity_after,
                    f'Sale {sale_row["saleNumber"]}',
                ),
            )

        conn.commit()
        return {
            "id": str(sale_row["id"]), "sale_number": sale_row["saleNumber"],
            "status": sale_row["status"], "subtotal": float(subtotal),
            "discount": float(sale.discount), "total": float(total),
            "created_at": utc_isoformat(sale_row["created_at"]),
            "allocations": len(allocations),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Sale could not be completed") from exc
    finally:
        cursor.close()
        conn.close()


@router.get("")
@limiter.limit("60/minute")
async def list_sales(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    user: dict = Depends(get_current_user),
):
    conditions = ['s."ownerId" = %s']
    params = [user["user_id"]]
    if date_from:
        conditions.append("s.created_at >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("s.created_at < %s::date + INTERVAL '1 day'")
        params.append(date_to)
    params.extend([limit, (page - 1) * limit])

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""SELECT s.*, COUNT(si.id) AS item_count, COUNT(*) OVER() AS total_count
                FROM "Sale" s
                LEFT JOIN "SaleItem" si ON si."saleId" = s.id
                WHERE {' AND '.join(conditions)}
                GROUP BY s.id ORDER BY s.created_at DESC LIMIT %s OFFSET %s;""",
            tuple(params),
        )
        rows = cursor.fetchall()
        return {
            "sales": [{
                "id": str(row["id"]), "sale_number": row["saleNumber"], "status": row["status"],
                "subtotal": float(row["subtotal"]), "discount": float(row["discount"]),
                "total": float(row["total"]), "notes": row["notes"],
                "item_count": row["item_count"], "created_at": utc_isoformat(row["created_at"]),
            } for row in rows],
            "total": rows[0]["total_count"] if rows else 0, "page": page, "limit": limit,
        }
    finally:
        cursor.close()
        conn.close()


@router.get("/{sale_id}")
@limiter.limit("60/minute")
async def get_sale(
    request: Request,
    sale_id: UUID,
    user: dict = Depends(get_current_user),
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM "Sale" WHERE id = %s AND "ownerId" = %s;', (str(sale_id), user["user_id"]))
        sale = cursor.fetchone()
        if not sale:
            raise HTTPException(status_code=404, detail="Sale not found")
        cursor.execute(
            """SELECT si.*, p.name AS product_name, b."batchNumber"
               FROM "SaleItem" si
               JOIN "Product" p ON p.id = si."productId" AND p."ownerId" = %s
               JOIN "Batch" b ON b.id = si."batchId" AND b."ownerId" = %s
               WHERE si."saleId" = %s ORDER BY p.name, b."expiryDate";""",
            (user["user_id"], user["user_id"], str(sale_id)),
        )
        items = cursor.fetchall()
        return {
            "id": str(sale["id"]), "sale_number": sale["saleNumber"], "status": sale["status"],
            "subtotal": float(sale["subtotal"]), "discount": float(sale["discount"]),
            "total": float(sale["total"]), "notes": sale["notes"],
            "created_at": utc_isoformat(sale["created_at"]),
            "items": [{
                "id": str(row["id"]), "product_id": str(row["productId"]),
                "product_name": row["product_name"], "batch_id": str(row["batchId"]),
                "batch_number": row["batchNumber"], "quantity": row["quantity"],
                "returned_quantity": row["returnedQuantity"], "unit_price": float(row["unitPrice"]),
                "line_total": float(row["lineTotal"]),
            } for row in items],
        }
    finally:
        cursor.close()
        conn.close()


@router.post("/{sale_id}/returns", status_code=201)
@limiter.limit("30/minute")
async def create_sales_return(
    request: Request,
    sale_id: UUID,
    sales_return: SalesReturnCreate,
    user: dict = Depends(get_current_user),
):
    owner_id = user["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, "saleNumber", subtotal, discount, total FROM "Sale" WHERE id = %s AND "ownerId" = %s FOR UPDATE;',
            (str(sale_id), owner_id),
        )
        sale = cursor.fetchone()
        if not sale:
            raise HTTPException(status_code=404, detail="Sale not found")

        item_ids = [str(line.sale_item_id) for line in sales_return.items]
        cursor.execute(
            """SELECT si.*, b.quantity AS batch_quantity
               FROM "SaleItem" si
               JOIN "Batch" b ON b.id = si."batchId" AND b."ownerId" = %s
               WHERE si."saleId" = %s AND si.id = ANY(%s::uuid[])
               FOR UPDATE OF si, b;""",
            (owner_id, str(sale_id), item_ids),
        )
        sale_items = {str(row["id"]): row for row in cursor.fetchall()}
        if set(item_ids) != set(sale_items):
            raise HTTPException(status_code=400, detail="One or more return lines are invalid")

        refund_ratio = Decimal("1") if sale["subtotal"] == 0 else sale["total"] / sale["subtotal"]
        prepared = []
        refund_total = Decimal("0")
        for line in sales_return.items:
            item = sale_items[str(line.sale_item_id)]
            available_to_return = item["quantity"] - item["returnedQuantity"]
            if line.quantity > available_to_return:
                raise HTTPException(
                    status_code=409,
                    detail=f"Return exceeds the {available_to_return} units remaining on a sale item",
                )
            amount = _money(item["unitPrice"] * line.quantity * refund_ratio)
            refund_total += amount
            prepared.append((line, item, amount))
        refund_total = _money(refund_total)

        cursor.execute(
            """INSERT INTO "SalesReturn" (
                   id, "returnNumber", "saleId", "ownerId", "receivedBy", reason, "refundAmount"
               ) VALUES (
                   gen_random_uuid(),
                   'RET-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || UPPER(SUBSTRING(REPLACE(gen_random_uuid()::text, '-', ''), 1, 6)),
                   %s, %s, %s, %s, %s
               ) RETURNING id, "returnNumber", created_at;""",
            (str(sale_id), owner_id, owner_id, sales_return.reason.strip(), refund_total),
        )
        return_row = cursor.fetchone()

        for line, item, amount in prepared:
            quantity_after = item["batch_quantity"] + line.quantity
            cursor.execute(
                'UPDATE "Batch" SET quantity = %s, updated_at = NOW() WHERE id = %s AND "ownerId" = %s;',
                (quantity_after, item["batchId"], owner_id),
            )
            cursor.execute(
                'UPDATE "SaleItem" SET "returnedQuantity" = "returnedQuantity" + %s WHERE id = %s;',
                (line.quantity, str(line.sale_item_id)),
            )
            cursor.execute(
                """INSERT INTO "SalesReturnItem" (
                       id, "returnId", "saleItemId", "batchId", quantity, "refundAmount"
                   ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s);""",
                (return_row["id"], str(line.sale_item_id), item["batchId"], line.quantity, amount),
            )
            cursor.execute(
                """INSERT INTO "StockMovement" (
                       id, "batchId", "productId", "ownerId", "createdBy",
                       "quantityChange", "quantityBefore", "quantityAfter", reason, note
                   ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, 'return', %s);""",
                (
                    item["batchId"], item["productId"], owner_id, owner_id, line.quantity,
                    item["batch_quantity"], quantity_after,
                    f'Sales return {return_row["returnNumber"]} for {sale["saleNumber"]}',
                ),
            )

        cursor.execute(
            'SELECT BOOL_AND("returnedQuantity" = quantity) AS fully_returned FROM "SaleItem" WHERE "saleId" = %s;',
            (str(sale_id),),
        )
        new_status = "refunded" if cursor.fetchone()["fully_returned"] else "partially_returned"
        cursor.execute('UPDATE "Sale" SET status = %s WHERE id = %s;', (new_status, str(sale_id)))
        conn.commit()
        return {
            "id": str(return_row["id"]), "return_number": return_row["returnNumber"],
            "sale_number": sale["saleNumber"], "sale_status": new_status,
            "refund_amount": float(refund_total), "created_at": utc_isoformat(return_row["created_at"]),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Sales return could not be completed") from exc
    finally:
        cursor.close()
        conn.close()
