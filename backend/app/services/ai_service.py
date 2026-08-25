import logging
from app.database import get_db_connection
from app.services.ai_client import get_groq_client, public_ai_error

logger = logging.getLogger("rxos.ai")

def generate_morning_briefing(owner_id: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        owner_filter = 'WHERE p."ownerId" = %s' if owner_id else ""
        params = (owner_id,) if owner_id else ()

        cursor.execute(f'SELECT COUNT(*) as total FROM "Product" p {owner_filter};', params)
        total_products = cursor.fetchone()["total"]

        cursor.execute(f"""
            SELECT p.name, SUM(b.quantity) as stock
            FROM "Product" p
            JOIN "Batch" b ON p.id = b."productId"
            {owner_filter}
            GROUP BY p.name, p."minStockLevel"
            HAVING SUM(b.quantity) <= p."minStockLevel";
        """, params)
        low_stock_items = cursor.fetchall()

        cursor.execute(f"""
            SELECT p.name, b."batchNumber", b."expiryDate", b.quantity
            FROM "Product" p
            JOIN "Batch" b ON p.id = b."productId"
            {owner_filter}
            {"AND " if owner_filter else "WHERE "} b."expiryDate" <= CURRENT_DATE + INTERVAL '90 days'
            ORDER BY b."expiryDate" ASC;
        """, params)
        expiring_items = cursor.fetchall()

        cursor.close()
        conn.close()

        data_summary = f"""
        Total SKU Types: {total_products}
        Low Stock Warnings: {[{'name': item['name'], 'qty': item['stock']} for item in low_stock_items]}
        Items Expiring Soon (90 Days): {[{'name': item['name'], 'batch': item['batchNumber'], 'expiry': str(item['expiryDate']), 'qty': item['quantity']} for item in expiring_items]}
        """

        response = get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an elite, highly concise AI Pharmacy Operations Manager. Your job is to read "
                        "the structured raw database metrics provided and write a sharp, punchy morning briefing "
                        "for the pharmacy owner. Do not use generic introductory filler phrases. Highlight immediate "
                        "financial actions, low stock items to reorder, and impending expiry risks clearly using markdown bullets."
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
