import logging
from app.database import get_db_connection
from app.services.ai_client import get_ai_model, get_groq_client, public_ai_error

logger = logging.getLogger("rxos.ai")

def generate_morning_briefing(owner_id: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        expiry_alert_days = 90
        if owner_id:
            cursor.execute(
                'SELECT expiry_alert_days FROM "PharmacyProfile" WHERE "ownerId" = %s;',
                (owner_id,),
            )
            profile = cursor.fetchone()
            if profile:
                expiry_alert_days = profile["expiry_alert_days"]

        owner_filter = 'WHERE p."ownerId" = %s AND p.is_active = TRUE' if owner_id else "WHERE p.is_active = TRUE"
        params = (owner_id,) if owner_id else ()

        cursor.execute(f'SELECT COUNT(*) as total FROM "Product" p {owner_filter};', params)
        total_products = cursor.fetchone()["total"]

        cursor.execute(f"""
            SELECT p.name, SUM(b.quantity) as stock
            FROM "Product" p
            JOIN "Batch" b ON p.id = b."productId" AND b.is_active = TRUE
            {owner_filter}
            GROUP BY p.name, p."minStockLevel"
            HAVING SUM(b.quantity) <= p."minStockLevel";
        """, params)
        low_stock_items = cursor.fetchall()

        cursor.execute(f"""
            SELECT p.name, b."batchNumber", b."expiryDate", b.quantity,
                   (b."expiryDate" - CURRENT_DATE) AS days_remaining
            FROM "Product" p
            JOIN "Batch" b ON p.id = b."productId" AND b.is_active = TRUE
            {owner_filter}
            {"AND " if owner_filter else "WHERE "} b."expiryDate" <= CURRENT_DATE + (%s * INTERVAL '1 day')
            ORDER BY b."expiryDate" ASC;
        """, params + (expiry_alert_days,))
        expiring_items = cursor.fetchall()

        cursor.close()
        conn.close()

        data_summary = f"""
        Total SKU Types: {total_products}
        Low Stock Warnings: {[{'name': item['name'], 'qty': item['stock']} for item in low_stock_items]}
        Items Expiring Soon ({expiry_alert_days} Day Alert Window): {[{'name': item['name'], 'batch': item['batchNumber'], 'expiry': str(item['expiryDate']), 'days_remaining': item['days_remaining'], 'qty': item['quantity']} for item in expiring_items]}
        """

        response = get_groq_client().chat.completions.create(
            model=get_ai_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an elite, highly concise AI Pharmacy Operations Manager. Your job is to read "
                        "the structured raw database metrics provided and write a sharp, punchy morning briefing "
                        "for the pharmacy owner. Do not use generic introductory filler phrases. Highlight immediate "
                        "financial actions, low stock items to reorder, and impending expiry risks clearly using markdown bullets. "
                        "Use the supplied days_remaining value exactly; never estimate or invent expiry timing."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Analyze this morning's pharmacy data pool and generate the summary update:\n{data_summary}",
                },
            ],
            temperature=0.3,
            max_tokens=500,
        )

        return {"status": "success", "briefing": response.choices[0].message.content}

    except Exception as e:
        logger.exception("Morning briefing failed")
        if "cursor" in locals() and not cursor.closed:
            cursor.close()
        if "conn" in locals() and conn:
            conn.close()
        return {"status": "error", "detail": public_ai_error(e)}
