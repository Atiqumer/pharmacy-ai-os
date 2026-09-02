from datetime import date
from decimal import Decimal
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
router = APIRouter(prefix="/purchasing", tags=["Purchasing"])


class PurchaseOrderLineCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)
    cost_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class PurchaseOrderCreate(BaseModel):
    supplier_id: UUID
    expected_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    items: list[PurchaseOrderLineCreate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def product_lines_must_be_unique(self):
        product_ids = [line.product_id for line in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Each product can appear only once in a purchase order")
        return self


class PurchaseOrderUpdate(PurchaseOrderCreate):
    pass


class ReceiptLine(BaseModel):
    purchase_order_item_id: UUID
    quantity: int = Field(gt=0)
    batch_number: str = Field(min_length=1, max_length=100)
    expiry_date: date
    retail_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class GoodsReceiptCreate(BaseModel):
    reference: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=500)
    items: list[ReceiptLine] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def receipt_lines_must_be_unique(self):
        line_ids = [line.purchase_order_item_id for line in self.items]
        if len(line_ids) != len(set(line_ids)):
            raise ValueError("Each purchase order line can appear only once per receipt")
        return self


@router.post("/orders", status_code=201)
@limiter.limit("20/minute")
async def create_purchase_order(
    request: Request,
    order: PurchaseOrderCreate,
    user: dict = Depends(get_current_user),
):
    owner_id = user["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id FROM "Supplier" WHERE id = %s AND "ownerId" = %s AND is_active = TRUE;',
            (str(order.supplier_id), owner_id),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Active supplier not found")

        product_ids = [str(line.product_id) for line in order.items]
        cursor.execute(
            'SELECT id FROM "Product" WHERE "ownerId" = %s AND is_active = TRUE AND id = ANY(%s::uuid[]);',
            (owner_id, product_ids),
        )
        found_products = {str(row["id"]) for row in cursor.fetchall()}
        if found_products != set(product_ids):
            raise HTTPException(status_code=400, detail="One or more products do not belong to this pharmacy")

        total_cost = sum(line.cost_price * line.quantity for line in order.items)
        cursor.execute(
            """INSERT INTO "PurchaseOrder" (
                   id, "orderNumber", "supplierId", "ownerId", "createdBy",
                   "expectedDate", notes, "totalCost"
               ) VALUES (
                   gen_random_uuid(),
                   'PO-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || UPPER(SUBSTRING(REPLACE(gen_random_uuid()::text, '-', ''), 1, 6)),
                   %s, %s, %s, %s, %s, %s
               ) RETURNING id, "orderNumber", status, "totalCost", created_at;""",
            (
                str(order.supplier_id), owner_id, owner_id, order.expected_date,
                order.notes.strip() if order.notes else None, total_cost,
            ),
        )
        purchase_order = cursor.fetchone()
        for line in order.items:
            cursor.execute(
                """INSERT INTO "PurchaseOrderItem" (
                       id, "purchaseOrderId", "productId", "orderedQuantity", "costPrice"
                   ) VALUES (gen_random_uuid(), %s, %s, %s, %s);""",
                (purchase_order["id"], str(line.product_id), line.quantity, line.cost_price),
            )
        conn.commit()
        return {
            "id": str(purchase_order["id"]),
            "order_number": purchase_order["orderNumber"],
            "status": purchase_order["status"],
            "total_cost": float(purchase_order["totalCost"]),
            "created_at": utc_isoformat(purchase_order["created_at"]),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Purchase order could not be created") from exc
    finally:
        cursor.close()
        conn.close()


@router.get("/orders")
@limiter.limit("30/minute")
async def list_purchase_orders(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: str = Query("all", alias="status", pattern="^(all|draft|ordered|partially_received|received|cancelled)$"),
    user: dict = Depends(get_current_user),
):
    conditions = ['po."ownerId" = %s']
    params = [user["user_id"]]
    if status_filter != "all":
        conditions.append("po.status = %s")
        params.append(status_filter)
    params.extend([limit, (page - 1) * limit])

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""SELECT
                    po.id, po."orderNumber", po.status, po."expectedDate", po."totalCost",
                    po.created_at, s.name AS supplier_name,
                    COUNT(poi.id) AS line_count,
                    COALESCE(SUM(poi."orderedQuantity"), 0) AS ordered_quantity,
                    COALESCE(SUM(poi."receivedQuantity"), 0) AS received_quantity,
                    COUNT(*) OVER() AS total_count
                FROM "PurchaseOrder" po
                JOIN "Supplier" s ON s.id = po."supplierId" AND s."ownerId" = po."ownerId"
                LEFT JOIN "PurchaseOrderItem" poi ON poi."purchaseOrderId" = po.id
                WHERE {' AND '.join(conditions)}
                GROUP BY po.id, s.name
                ORDER BY po.created_at DESC
                LIMIT %s OFFSET %s;""",
            tuple(params),
        )
        rows = cursor.fetchall()
        return {
            "orders": [{
                "id": str(row["id"]), "order_number": row["orderNumber"],
                "supplier_name": row["supplier_name"], "status": row["status"],
                "expected_date": str(row["expectedDate"]) if row["expectedDate"] else None,
                "total_cost": float(row["totalCost"]), "line_count": row["line_count"],
                "ordered_quantity": row["ordered_quantity"], "received_quantity": row["received_quantity"],
                "created_at": utc_isoformat(row["created_at"]),
            } for row in rows],
            "total": rows[0]["total_count"] if rows else 0,
            "page": page, "limit": limit,
        }
    finally:
        cursor.close()
        conn.close()


@router.put("/orders/{order_id}")
@limiter.limit("20/minute")
async def update_purchase_order(
    request: Request,
    order_id: UUID,
    order: PurchaseOrderUpdate,
    user: dict = Depends(get_current_user),
):
    owner_id = user["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id FROM "PurchaseOrder" WHERE id = %s AND "ownerId" = %s AND status = \'draft\' FOR UPDATE;',
            (str(order_id), owner_id),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=409, detail="Only a draft purchase order can be edited")
        cursor.execute(
            'SELECT id FROM "Supplier" WHERE id = %s AND "ownerId" = %s AND is_active = TRUE;',
            (str(order.supplier_id), owner_id),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Active supplier not found")
        product_ids = [str(line.product_id) for line in order.items]
        cursor.execute(
            'SELECT id FROM "Product" WHERE "ownerId" = %s AND is_active = TRUE AND id = ANY(%s::uuid[]);',
            (owner_id, product_ids),
        )
        if {str(row["id"]) for row in cursor.fetchall()} != set(product_ids):
            raise HTTPException(status_code=400, detail="One or more active products do not belong to this pharmacy")

        total_cost = sum(line.cost_price * line.quantity for line in order.items)
        cursor.execute(
            """UPDATE "PurchaseOrder"
               SET "supplierId" = %s, "expectedDate" = %s, notes = %s,
                   "totalCost" = %s, updated_at = NOW()
               WHERE id = %s AND "ownerId" = %s;""",
            (
                str(order.supplier_id), order.expected_date,
                order.notes.strip() if order.notes else None, total_cost,
                str(order_id), owner_id,
            ),
        )
        cursor.execute('DELETE FROM "PurchaseOrderItem" WHERE "purchaseOrderId" = %s;', (str(order_id),))
        for line in order.items:
            cursor.execute(
                """INSERT INTO "PurchaseOrderItem" (
                       id, "purchaseOrderId", "productId", "orderedQuantity", "costPrice"
                   ) VALUES (gen_random_uuid(), %s, %s, %s, %s);""",
                (str(order_id), str(line.product_id), line.quantity, line.cost_price),
            )
        conn.commit()
        return {"message": "Draft purchase order updated", "id": str(order_id), "total_cost": float(total_cost)}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Purchase order could not be updated") from exc
    finally:
        cursor.close()
        conn.close()


@router.get("/orders/{order_id}")
@limiter.limit("30/minute")
async def get_purchase_order(
    request: Request,
    order_id: UUID,
    user: dict = Depends(get_current_user),
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT po.*, s.name AS supplier_name
               FROM "PurchaseOrder" po
               JOIN "Supplier" s ON s.id = po."supplierId"
               WHERE po.id = %s AND po."ownerId" = %s;""",
            (str(order_id), user["user_id"]),
        )
        order = cursor.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        cursor.execute(
            """SELECT poi.id, poi."productId", p.name, poi."orderedQuantity",
                      poi."receivedQuantity", poi."costPrice"
               FROM "PurchaseOrderItem" poi
               JOIN "Product" p ON p.id = poi."productId" AND p."ownerId" = %s
               WHERE poi."purchaseOrderId" = %s ORDER BY p.name;""",
            (user["user_id"], str(order_id)),
        )
        items = cursor.fetchall()
        return {
            "id": str(order["id"]), "order_number": order["orderNumber"],
            "supplier_id": str(order["supplierId"]), "supplier_name": order["supplier_name"],
            "status": order["status"],
            "expected_date": str(order["expectedDate"]) if order["expectedDate"] else None,
            "notes": order["notes"], "total_cost": float(order["totalCost"]),
            "created_at": utc_isoformat(order["created_at"]),
            "items": [{
                "id": str(row["id"]), "product_id": str(row["productId"]),
                "product_name": row["name"], "ordered_quantity": row["orderedQuantity"],
                "received_quantity": row["receivedQuantity"], "cost_price": float(row["costPrice"]),
            } for row in items],
        }
    finally:
        cursor.close()
        conn.close()


@router.post("/orders/{order_id}/submit")
@limiter.limit("20/minute")
async def submit_purchase_order(
    request: Request,
    order_id: UUID,
    user: dict = Depends(get_current_user),
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE "PurchaseOrder" SET status = 'ordered', updated_at = NOW()
               WHERE id = %s AND "ownerId" = %s AND status = 'draft'
               RETURNING "orderNumber";""",
            (str(order_id), user["user_id"]),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=409, detail="Only a draft purchase order can be submitted")
        conn.commit()
        return {"message": "Purchase order submitted", "order_number": row["orderNumber"], "status": "ordered"}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


@router.post("/orders/{order_id}/cancel")
@limiter.limit("20/minute")
async def cancel_purchase_order(
    request: Request,
    order_id: UUID,
    user: dict = Depends(get_current_user),
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE "PurchaseOrder" po
               SET status = 'cancelled', updated_at = NOW()
               WHERE po.id = %s AND po."ownerId" = %s
                 AND po.status IN ('draft', 'ordered')
                 AND NOT EXISTS (
                     SELECT 1 FROM "PurchaseOrderItem" poi
                     WHERE poi."purchaseOrderId" = po.id AND poi."receivedQuantity" > 0
                 )
               RETURNING po."orderNumber";""",
            (str(order_id), user["user_id"]),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=409,
                detail="Only an unreceived draft or ordered purchase order can be cancelled",
            )
        conn.commit()
        return {"message": "Purchase order cancelled", "order_number": row["orderNumber"], "status": "cancelled"}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


@router.post("/orders/{order_id}/receive")
@limiter.limit("20/minute")
async def receive_purchase_order(
    request: Request,
    order_id: UUID,
    receipt: GoodsReceiptCreate,
    user: dict = Depends(get_current_user),
):
    owner_id = user["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT id, "supplierId", "orderNumber", status
               FROM "PurchaseOrder"
               WHERE id = %s AND "ownerId" = %s FOR UPDATE;""",
            (str(order_id), owner_id),
        )
        order = cursor.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        if order["status"] not in ("ordered", "partially_received"):
            raise HTTPException(status_code=409, detail="This purchase order cannot receive stock in its current status")

        line_ids = [str(line.purchase_order_item_id) for line in receipt.items]
        cursor.execute(
            """SELECT id, "productId", "orderedQuantity", "receivedQuantity", "costPrice"
               FROM "PurchaseOrderItem"
               WHERE "purchaseOrderId" = %s AND id = ANY(%s::uuid[])
               FOR UPDATE;""",
            (str(order_id), line_ids),
        )
        order_lines = {str(row["id"]): row for row in cursor.fetchall()}
        if set(line_ids) != set(order_lines):
            raise HTTPException(status_code=400, detail="One or more receipt lines are invalid")

        for line in receipt.items:
            order_line = order_lines[str(line.purchase_order_item_id)]
            remaining = order_line["orderedQuantity"] - order_line["receivedQuantity"]
            if line.quantity > remaining:
                raise HTTPException(
                    status_code=409,
                    detail=f"Receipt quantity exceeds the {remaining} units remaining on an order line",
                )

        cursor.execute(
            """INSERT INTO "GoodsReceipt" (
                   id, "purchaseOrderId", "ownerId", "receivedBy", reference, notes
               ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s) RETURNING id, received_at;""",
            (
                str(order_id), owner_id, owner_id, receipt.reference,
                receipt.notes.strip() if receipt.notes else None,
            ),
        )
        receipt_row = cursor.fetchone()

        for line in receipt.items:
            order_line = order_lines[str(line.purchase_order_item_id)]
            cursor.execute(
                """INSERT INTO "Batch" (
                       id, "batchNumber", "productId", "supplierId", quantity,
                       "costPrice", "retailPrice", "expiryDate", "ownerId"
                   ) VALUES (gen_random_uuid(), %s, %s, %s, 0, %s, %s, %s, %s)
                   ON CONFLICT ("ownerId", "productId", "batchNumber") DO UPDATE SET
                     "supplierId" = EXCLUDED."supplierId",
                     "costPrice" = EXCLUDED."costPrice",
                     "retailPrice" = EXCLUDED."retailPrice",
                     "expiryDate" = EXCLUDED."expiryDate"
                   RETURNING id, quantity;""",
                (
                    line.batch_number.strip(), order_line["productId"], order["supplierId"],
                    order_line["costPrice"], line.retail_price, line.expiry_date, owner_id,
                ),
            )
            batch = cursor.fetchone()
            quantity_before = batch["quantity"]
            quantity_after = quantity_before + line.quantity
            cursor.execute('UPDATE "Batch" SET quantity = %s WHERE id = %s;', (quantity_after, batch["id"]))
            cursor.execute(
                """UPDATE "PurchaseOrderItem"
                   SET "receivedQuantity" = "receivedQuantity" + %s WHERE id = %s;""",
                (line.quantity, str(line.purchase_order_item_id)),
            )
            cursor.execute(
                """INSERT INTO "StockMovement" (
                       id, "batchId", "productId", "ownerId", "createdBy",
                       "quantityChange", "quantityBefore", "quantityAfter", reason, note
                   ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, 'purchase', %s);""",
                (
                    batch["id"], order_line["productId"], owner_id, owner_id, line.quantity,
                    quantity_before, quantity_after, f'Goods receipt for {order["orderNumber"]}',
                ),
            )
            cursor.execute(
                """INSERT INTO "GoodsReceiptItem" (
                       id, "receiptId", "purchaseOrderItemId", "batchId", quantity
                   ) VALUES (gen_random_uuid(), %s, %s, %s, %s);""",
                (receipt_row["id"], str(line.purchase_order_item_id), batch["id"], line.quantity),
            )

        cursor.execute(
            """SELECT BOOL_AND("receivedQuantity" = "orderedQuantity") AS complete
               FROM "PurchaseOrderItem" WHERE "purchaseOrderId" = %s;""",
            (str(order_id),),
        )
        new_status = "received" if cursor.fetchone()["complete"] else "partially_received"
        cursor.execute(
            'UPDATE "PurchaseOrder" SET status = %s, updated_at = NOW() WHERE id = %s;',
            (new_status, str(order_id)),
        )
        conn.commit()
        return {
            "message": "Goods receipt posted",
            "receipt_id": str(receipt_row["id"]),
            "status": new_status,
            "received_at": utc_isoformat(receipt_row["received_at"]),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Goods receipt could not be posted") from exc
    finally:
        cursor.close()
        conn.close()
