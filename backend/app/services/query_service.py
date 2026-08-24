import os
import re
import logging
import sqlparse
from groq import Groq
from app.database import get_db_connection

logger = logging.getLogger("rxos.query")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

ALLOWED_TABLES = {"Product", "Batch", "Supplier"}

BLOCKED_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
    "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "CALL",
    "INTO", "SET", "MERGE", "UPSERT", "COPY", "COMMIT", "ROLLBACK",
}


def _validate_sql(sql: str) -> str:
    parsed = sqlparse.parse(sql)
    if not parsed:
        raise ValueError("Empty SQL query")

    stmt = parsed[0]
    stmt_type = stmt.get_type()

    if stmt_type and stmt_type.upper() != "SELECT":
        raise ValueError(f"Only SELECT queries are permitted. Detected: {stmt_type}")

    upper = sql.upper()
    for keyword in BLOCKED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper):
            raise ValueError(f"Blocked keyword detected: {keyword}")

    table_pattern = r'(?:FROM|JOIN)\s+"?(\w+)"?'
    referenced_tables = set(re.findall(table_pattern, sql, re.IGNORECASE))
    for table in referenced_tables:
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Referenced table '{table}' is not in the allowed list.")

    return sql.strip().rstrip(";").strip()


def execute_natural_query(user_question: str, owner_id: str = None):
    schema_context = """
    You are a secure database translation engine. Translate the user's plain English request into a valid PostgreSQL query.
    
    Tables available:
    - "Product" (id UUID, name VARCHAR, "genericName" VARCHAR, category VARCHAR, "minStockLevel" INT, "ownerId" UUID)
    - "Batch" (id UUID, "batchNumber" VARCHAR, "productId" UUID, "supplierId" UUID, quantity INT, "costPrice" FLOAT, "retailPrice" FLOAT, "expiryDate" DATE, "ownerId" UUID)
    - "Supplier" (id UUID, name VARCHAR, "ownerId" UUID)
    
    Rules:
    1. Respond ONLY with a single executable SELECT query. No explanations, no markdown, no code fences.
    2. Never generate destructive commands. Only SELECT queries.
    3. Use exact casing for table names and column names inside double quotes where specified.
    4. Always filter by "ownerId" = '{owner_id}' in every FROM/JOIN clause to scope results to the current user.
    5. Always alias aggregate columns for readability.
    6. Limit results to 100 rows maximum unless the user specifies otherwise.
    """

    if owner_id:
        schema_context = schema_context.replace("{owner_id}", owner_id)
    else:
        schema_context = schema_context.replace("Always filter by \"ownerId\" = '{owner_id}' in every FROM/JOIN clause to scope results to the current user.", "")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": schema_context},
                {"role": "user", "content": f"Translate this request to SQL: {user_question}"},
            ],
            temperature=0.1,
        )

        sql_query = response.choices[0].message.content.strip()
        sql_query = re.sub(r"```sql|```", "", sql_query).strip()

        sql_query = _validate_sql(sql_query)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return {"status": "success", "query_generated": sql_query, "data": rows}

    except ValueError as e:
        logger.warning(f"Query rejected: {e}")
        return {"status": "error", "detail": f"Query rejected: {str(e)}"}
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return {"status": "error", "detail": str(e)}
