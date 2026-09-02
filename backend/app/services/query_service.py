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

LOW_STOCK_PATTERNS = (
    r"\blow stock\b",
    r"\brunning low\b",
    r"\bbelow (?:the )?minimum\b",
    r"\bunder (?:the )?minimum\b",
    r"\bneeds? (?:reorder|restock(?:ing)?)\b",
    r"\breorder (?:list|suggestions?)\b",
)
OUT_OF_STOCK_PATTERNS = (
    r"\bout of stock\b",
    r"\bno stock\b",
    r"\bzero stock\b",
    r"\bsold out\b",
)
EXPIRED_PATTERNS = (
    r"\bexpired\b",
    r"\bpast (?:the )?expir(?:y|ation)\b",
)
EXPIRING_PATTERNS = (
    r"\bexpir(?:e|es|ing|y)\b",
    r"\bnear expir(?:y|ation)\b",
)


def _matches_any(question: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, question, re.IGNORECASE) for pattern in patterns)


def _deterministic_query(user_question: str, owner_id: str) -> str | None:
    """Return trusted SQL for common pharmacy intents; otherwise use the AI translator."""
    normalized_owner_id = str(UUID(owner_id))
    question = " ".join(user_question.strip().split())

    product_stock_select = f"""
        SELECT
            p.id AS product_id,
            p.name AS product_name,
            p."genericName" AS generic_name,
            p.category,
            p."minStockLevel" AS min_stock_level,
            COALESCE(SUM(b.quantity), 0) AS total_quantity
        FROM "Product" AS p
        LEFT JOIN "Batch" AS b
          ON b."productId" = p.id
         AND b."ownerId" = '{normalized_owner_id}'
         AND b.is_active = TRUE
        WHERE p."ownerId" = '{normalized_owner_id}'
          AND p.is_active = TRUE
        GROUP BY p.id, p.name, p."genericName", p.category, p."minStockLevel"
    """

    if _matches_any(question, OUT_OF_STOCK_PATTERNS):
        return _validate_sql(
            product_stock_select
            + """
                HAVING COALESCE(SUM(b.quantity), 0) <= 0
                ORDER BY p.name
                LIMIT 100
            """,
            normalized_owner_id,
        )

    if _matches_any(question, LOW_STOCK_PATTERNS):
        return _validate_sql(
            product_stock_select
            + """
                HAVING COALESCE(SUM(b.quantity), 0) <= p."minStockLevel"
                ORDER BY (p."minStockLevel" - COALESCE(SUM(b.quantity), 0)) DESC, p.name
                LIMIT 100
            """,
            normalized_owner_id,
        )

    if _matches_any(question, EXPIRED_PATTERNS):
        return _validate_sql(
            f"""
                SELECT
                    p.name AS product_name,
                    p."genericName" AS generic_name,
                    b."batchNumber" AS batch_number,
                    b.quantity,
                    b."expiryDate" AS expiry_date
                FROM "Batch" AS b
                JOIN "Product" AS p
                  ON p.id = b."productId"
                 AND p."ownerId" = '{normalized_owner_id}'
                 AND p.is_active = TRUE
                WHERE b."ownerId" = '{normalized_owner_id}'
                  AND b.is_active = TRUE
                  AND b."expiryDate" < CURRENT_DATE
                ORDER BY b."expiryDate" ASC, p.name
                LIMIT 100
            """,
            normalized_owner_id,
        )

    if _matches_any(question, EXPIRING_PATTERNS):
        days_match = re.search(r"\b(\d{1,3})\s*(?:day|days|d)\b", question, re.IGNORECASE)
        days = min(max(int(days_match.group(1)), 1), 365) if days_match else 90
        return _validate_sql(
            f"""
                SELECT
                    p.name AS product_name,
                    p."genericName" AS generic_name,
                    b."batchNumber" AS batch_number,
                    b.quantity,
                    b."costPrice" AS cost_price,
                    b."retailPrice" AS retail_price,
                    b."expiryDate" AS expiry_date
                FROM "Batch" AS b
                JOIN "Product" AS p
                  ON p.id = b."productId"
                 AND p."ownerId" = '{normalized_owner_id}'
                 AND p.is_active = TRUE
                WHERE b."ownerId" = '{normalized_owner_id}'
                  AND b.is_active = TRUE
                  AND b."expiryDate" BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '{days} days'
                ORDER BY b."expiryDate" ASC, p.name
                LIMIT 100
            """,
            normalized_owner_id,
        )

    return None


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
    - "Product" (id UUID, name VARCHAR, "genericName" VARCHAR, category VARCHAR, "minStockLevel" INT, is_active BOOLEAN, "ownerId" UUID)
    - "Batch" (id UUID, "batchNumber" VARCHAR, "productId" UUID, "supplierId" UUID, quantity INT, "costPrice" FLOAT, "retailPrice" FLOAT, "expiryDate" DATE, is_active BOOLEAN, "ownerId" UUID)
    - "Supplier" (id UUID, name VARCHAR, is_active BOOLEAN, "ownerId" UUID)
    
    Rules:
    1. Respond ONLY with a single executable SELECT query. No explanations, no markdown, no code fences.
    2. Never generate destructive commands. Only SELECT queries.
    3. Use exact casing for table names and column names inside double quotes where specified.
    4. Every table MUST use an explicit short alias, for example: FROM "Product" AS p.
    5. For EVERY table alias, add an exact filter: alias."ownerId" = '{owner_id}'. This applies to joined tables too.
    6. Always alias aggregate columns for readability.
    7. Limit results to 100 rows maximum.
    8. Treat "low stock" or "running low" as total active batch quantity less than or equal to the product's "minStockLevel".
    9. Treat "expiring" as not yet expired. Use CURRENT_DATE through the requested future window, defaulting to 90 days.
    10. Exclude inactive products and batches unless the user explicitly requests archived data.

    Example low-stock shape:
    SELECT p.name AS product_name, p."minStockLevel" AS min_stock_level,
           COALESCE(SUM(b.quantity), 0) AS total_quantity
    FROM "Product" AS p
    LEFT JOIN "Batch" AS b ON b."productId" = p.id
      AND b."ownerId" = '{owner_id}' AND b.is_active = TRUE
    WHERE p."ownerId" = '{owner_id}' AND p.is_active = TRUE
    GROUP BY p.id, p.name, p."minStockLevel"
    HAVING COALESCE(SUM(b.quantity), 0) <= p."minStockLevel"
    LIMIT 100
    """

    if owner_id:
        schema_context = schema_context.replace("{owner_id}", owner_id)
    else:
        schema_context = schema_context.replace("Always filter by \"ownerId\" = '{owner_id}' in every FROM/JOIN clause to scope results to the current user.", "")

    try:
        sql_query = _deterministic_query(user_question, owner_id) if owner_id else None
    except (TypeError, ValueError) as exc:
        logger.warning("Deterministic query rejected: %s", exc)
        return {"status": "error", "detail": f"Query rejected: {str(exc)}"}

    if sql_query is None:
        try:
            response = get_groq_client().chat.completions.create(
                model=get_ai_model(),
                messages=[
                    {"role": "system", "content": schema_context},
                    {"role": "user", "content": f"Translate this request to SQL: {user_question}"},
                ],
                temperature=0.1,
            )
        except Exception as exc:
            logger.exception("AI translation request failed")
            return {"status": "error", "detail": public_ai_error(exc)}

        try:
            sql_query = response.choices[0].message.content.strip()
            sql_query = re.sub(r"```sql|```", "", sql_query).strip()
            sql_query = _validate_sql(sql_query, owner_id)
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            logger.warning("Generated query rejected: %s", exc)
            return {"status": "error", "detail": f"Query rejected: {str(exc)}"}

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute("SET LOCAL statement_timeout = '5s'")
        cursor.execute(sql_query)
        rows = cursor.fetchmany(101)
        if len(rows) > 100:
            rows = rows[:100]

        return {"status": "success", "query_generated": sql_query, "data": rows}
    except Exception:
        logger.exception("Generated inventory query execution failed")
        return {
            "status": "error",
            "detail": "The generated inventory query could not be executed. Try rephrasing the request.",
        }
    finally:
        if conn is not None:
            conn.rollback()
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
