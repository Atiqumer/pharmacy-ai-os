import os
import re
from groq import Groq
from app.database import get_db_connection

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def execute_natural_query(user_question: str):
    # 1. Provide the exact database schema to the LLM so it writes accurate SQL
    schema_context = """
    You are a secure database translation engine. Translate the user's plain English request into a valid PostgreSQL query.
    
    Tables available:
    - "Product" (id UUID, name VARCHAR, "genericName" VARCHAR, category VARCHAR, "minStockLevel" INT)
    - "Batch" (id UUID, "batchNumber" VARCHAR, "productId" UUID, quantity INT, "costPrice" FLOAT, "retailPrice" FLOAT, "expiryDate" DATE)
    - "Supplier" (id UUID, name VARCHAR)
    
    Rules:
    1. Respond ONLY with the executable SQL string inside an instruction block. No explanations, no markdown formatting notes.
    2. Never execute destructive commands (DROP, DELETE, UPDATE, INSERT). Only generate SELECT queries.
    3. Use exact casing for table names and column overrides inside double quotes where specified by the schema.
    """
    
    try:
        # 2. Let the LLM construct the raw SQL string
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": schema_context},
                {"role": "user", "content": f"Translate this request to SQL: {user_question}"}
            ],
            temperature=0.1 # Low temperature ensures strict structural output
        )
        
        sql_query = response.choices[0].message.content.strip()
        
        # Strip out any markdown wrapper markers if the LLM accidentally included them
        sql_query = re.sub(r'```sql|```', '', sql_query).strip()
        
        # 3. Securely connect and execute the generated SQL query
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {"status": "success", "query_generated": sql_query, "data": rows}
        
    except Exception as e:
        return {"status": "error", "detail": str(e)}