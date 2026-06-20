import os
from groq import Groq
from app.database import get_db_connection

# Initialize the Groq client securely using your environment key
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_morning_briefing():  # <-- Check this spelling closely!
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Fetch raw data: Count total distinct medicines
        cursor.execute("SELECT COUNT(*) as total FROM \"Product\";")
        total_products = cursor.fetchone()['total']
        
        # 2. Fetch raw data: Identify items running lower than their safety stock limit
        cursor.execute("""
            SELECT p.name, SUM(b.quantity) as stock 
            FROM \"Product\" p 
            JOIN \"Batch\" b ON p.id = b."productId" 
            GROUP BY p.name, p."minStockLevel"
            HAVING SUM(b.quantity) <= p."minStockLevel";
        """)
        low_stock_items = cursor.fetchall()
        
        # 3. Fetch raw data: Identify items expiring within the next 90 days
        cursor.execute("""
            SELECT p.name, b."batchNumber", b."expiryDate", b.quantity 
            FROM \"Product\" p 
            JOIN \"Batch\" b ON p.id = b."productId" 
            WHERE b."expiryDate" <= CURRENT_DATE + INTERVAL '90 days'
            ORDER BY b."expiryDate" ASC;
        """)
        expiring_items = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # 4. Construct a concise data payload to send to the LLM
        data_summary = f"""
        Total SKU Types: {total_products}
        Low Stock Warnings: {[{'name': item['name'], 'qty': item['stock']} for item in low_stock_items]}
        Items Expiring Soon (90 Days): {[{'name': item['name'], 'batch': item['batchNumber'], 'expiry': str(item['expiryDate']), 'qty': item['quantity']} for item in expiring_items]}
        """
        
        # 5. Call Llama 3 via Groq to convert numbers into operational insights
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an elite, highly concise AI Pharmacy Operations Manager. Your job is to read "
                        "the structured raw database metrics provided and write a sharp, punchy morning briefing "
                        "for the pharmacy owner. Do not use generic introductory filler phrases. Highlight immediate "
                        "financial actions, low stock items to reorder, and impending expiry risks clearly using markdown bullets."
                    )
                },
                {
                    "role": "user",
                    "content": f"Analyze this morning's pharmacy data pool and generate the summary update:\n{data_summary}"
                }
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        return {"status": "success", "briefing": response.choices[0].message.content}
        
    except Exception as e:
        if 'cursor' in locals() and not cursor.closed:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
        return {"status": "error", "detail": str(e)}