import re
import logging
import sqlparse
from uuid import UUID
from app.database import get_db_connection
from app.services.ai_client import get_ai_model, get_groq_client, public_ai_error

logger = logging.getLogger("rxos.query")

ALLOWED_TABLES = {"Product", "Batch", "Supplier"}

BLOCKED_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
    "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "CALL",
    "INTO", "SET", "MERGE", "UPSERT", "COPY", "COMMIT", "ROLLBACK",
}


TABLE_REFERENCE_PATTERN = re.compile(
    r'(?:FROM|JOIN)\s+"?(Product|Batch|Supplier)"?\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*)',
    re.IGNORECASE,
)


def _validate_sql(sql: str, owner_id: str = None) -> str:
    parsed = sqlparse.parse(sql)
    if not parsed or not sql.strip():
        raise ValueError("Empty SQL query")
    if len(parsed) != 1:
        raise ValueError("Only one SQL statement is permitted")
    if "--" in sql or "/*" in sql or "*/" in sql:
        raise ValueError("SQL comments are not permitted")

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
    if not referenced_tables:
        raise ValueError("A query must reference an allowed inventory table")
    for table in referenced_tables:
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Referenced table '{table}' is not in the allowed list.")

    if owner_id:
        try:
            normalized_owner_id = str(UUID(owner_id))
        except (TypeError, ValueError):
            raise ValueError("Invalid inventory owner identifier")

        references = TABLE_REFERENCE_PATTERN.findall(sql)
        if len(references) != len(referenced_tables):
            raise ValueError("Every inventory table must use an explicit alias")

        for _, alias in references:
            owner_filter = re.compile(
                rf'\b{re.escape(alias)}\."ownerId"\s*=\s*\'{re.escape(normalized_owner_id)}\'',
                re.IGNORECASE,
            )
            if not owner_filter.search(sql):
                raise ValueError(f"Missing tenant filter for table alias '{alias}'")

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
    4. Every table MUST use an explicit short alias, for example: FROM "Product" AS p.
    5. For EVERY table alias, add an exact filter: alias."ownerId" = '{owner_id}'. This applies to joined tables too.
    6. Always alias aggregate columns for readability.
    7. Limit results to 100 rows maximum.
    """

    if owner_id:
        schema_context = schema_context.replace("{owner_id}", owner_id)
    else:
        schema_context = schema_context.replace("Always filter by \"ownerId\" = '{owner_id}' in every FROM/JOIN clause to scope results to the current user.", "")

    try:
        response = get_groq_client().chat.completions.create(
            model=get_ai_model(),
            messages=[
                {"role": "system", "content": schema_context},
                {"role": "user", "content": f"Translate this request to SQL: {user_question}"},
            ],
            temperature=0.1,
        )

        sql_query = response.choices[0].message.content.strip()
        sql_query = re.sub(r"```sql|```", "", sql_query).strip()

        sql_query = _validate_sql(sql_query, owner_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute(sql_query)
            rows = cursor.fetchmany(101)
            if len(rows) > 100:
                rows = rows[:100]
        finally:
            conn.rollback()
            cursor.close()
            conn.close()

        return {"status": "success", "query_generated": sql_query, "data": rows}

    except ValueError as e:
        logger.warning(f"Query rejected: {e}")
        return {"status": "error", "detail": f"Query rejected: {str(e)}"}
    except Exception as e:
        logger.exception("Query execution failed")
        return {"status": "error", "detail": public_ai_error(e)}
