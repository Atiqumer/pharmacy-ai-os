import csv
import io
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db_connection
from app.services.auth import get_current_user

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/reports", tags=["Reports"])


def _csv_response(filename: str, headers: list[str], rows: list[dict]):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/summary")
@limiter.limit("30/minute")
async def operational_summary(
    request: Request,
    date_from: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    date_to: date = Query(default_factory=date.today),
    user: dict = Depends(get_current_user),
):
    owner_id = user["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT COUNT(*) AS sale_count,
                      COALESCE(SUM(total), 0) AS sales_total,
                      COALESCE(SUM(discount), 0) AS discounts
               FROM "Sale"
               WHERE "ownerId" = %s AND created_at >= %s
                 AND created_at < %s::date + INTERVAL '1 day';""",
            (owner_id, date_from, date_to),
        )
        sales = cursor.fetchone()
        cursor.execute(
            """SELECT COALESCE(SUM((si.quantity - si."returnedQuantity") * si."costPrice"), 0) AS cost_of_goods,
                      COALESCE(SUM((si.quantity - si."returnedQuantity") * si."unitPrice"), 0) AS gross_item_revenue,
                      COALESCE(SUM(si."returnedQuantity" * si."unitPrice"), 0) AS gross_returned_value
               FROM "SaleItem" si
               JOIN "Sale" s ON s.id = si."saleId"
               WHERE s."ownerId" = %s AND s.created_at >= %s
                 AND s.created_at < %s::date + INTERVAL '1 day';""",
            (owner_id, date_from, date_to),
        )
        margins = cursor.fetchone()
        cursor.execute(
            """SELECT COALESCE(SUM("refundAmount"), 0) AS refunds
               FROM "SalesReturn"
               WHERE "ownerId" = %s AND created_at >= %s
                 AND created_at < %s::date + INTERVAL '1 day';""",
            (owner_id, date_from, date_to),
        )
        refunds = cursor.fetchone()["refunds"]
        cursor.execute(
            """SELECT COUNT(*) FILTER (WHERE status IN ('draft','ordered','partially_received')) AS open_orders,
                      COALESCE(SUM("totalCost") FILTER (WHERE status IN ('draft','ordered','partially_received')), 0) AS open_order_value
               FROM "PurchaseOrder" WHERE "ownerId" = %s;""",
            (owner_id,),
        )
        purchasing = cursor.fetchone()
        net_sales = sales["sales_total"] - refunds
        estimated_profit = net_sales - margins["cost_of_goods"]
        return {
            "date_from": str(date_from), "date_to": str(date_to),
            "sale_count": sales["sale_count"], "gross_sales": float(sales["sales_total"]),
            "refunds": float(refunds), "sales_total": float(net_sales),
            "discounts": float(sales["discounts"]),
            "cost_of_goods": float(margins["cost_of_goods"]),
            "estimated_gross_profit": float(estimated_profit),
            "open_purchase_orders": purchasing["open_orders"],
            "open_order_value": float(purchasing["open_order_value"]),
        }
    finally:
        cursor.close()
        conn.close()


@router.get("/inventory.csv")
@limiter.limit("10/minute")
async def export_inventory_csv(request: Request, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT p.name AS product_name, p."genericName" AS generic_name,
                      p.category, p.sku, p.barcode, p.manufacturer, p.strength,
                      p.dosage_form, p."minStockLevel" AS min_stock_level,
                      b."batchNumber" AS batch_number, b.quantity,
                      b."costPrice" AS cost_price, b."retailPrice" AS retail_price,
                      b."expiryDate" AS expiry_date, s.name AS supplier_name
               FROM "Batch" b
               JOIN "Product" p ON p.id = b."productId" AND p."ownerId" = b."ownerId"
               LEFT JOIN "Supplier" s ON s.id = b."supplierId" AND s."ownerId" = b."ownerId"
               WHERE b."ownerId" = %s AND p.is_active = TRUE AND b.is_active = TRUE
               ORDER BY p.name, b."expiryDate";""",
            (user["user_id"],),
        )
        headers = [
            "product_name", "generic_name", "category", "sku", "barcode", "manufacturer",
            "strength", "dosage_form", "min_stock_level", "batch_number", "quantity",
            "cost_price", "retail_price", "expiry_date", "supplier_name",
        ]
        return _csv_response(f"rxos-inventory-{date.today()}.csv", headers, cursor.fetchall())
    finally:
        cursor.close()
        conn.close()


@router.get("/sales.csv")
@limiter.limit("10/minute")
async def export_sales_csv(
    request: Request,
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
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""SELECT s."saleNumber" AS sale_number, s.created_at, s.status,
                       p.name AS product_name, b."batchNumber" AS batch_number,
                       si.quantity, si."returnedQuantity" AS returned_quantity,
                       si."unitPrice" AS unit_price, si."costPrice" AS cost_price,
                       si."lineTotal" AS line_total, s.discount AS sale_discount,
                       s.total AS sale_total
                FROM "Sale" s
                JOIN "SaleItem" si ON si."saleId" = s.id
                JOIN "Product" p ON p.id = si."productId" AND p."ownerId" = s."ownerId"
                JOIN "Batch" b ON b.id = si."batchId" AND b."ownerId" = s."ownerId"
                WHERE {' AND '.join(conditions)} ORDER BY s.created_at DESC, p.name;""",
            tuple(params),
        )
        headers = [
            "sale_number", "created_at", "status", "product_name", "batch_number", "quantity",
            "returned_quantity", "unit_price", "cost_price", "line_total", "sale_discount", "sale_total",
        ]
        return _csv_response(f"rxos-sales-{date.today()}.csv", headers, cursor.fetchall())
    finally:
        cursor.close()
        conn.close()
