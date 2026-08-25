import os
import uuid

import psycopg2
import pytest


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_connection():
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")
    connection = psycopg2.connect(os.environ["DATABASE_URL"])
    yield connection
    connection.close()


def test_migrations_created_expected_schema(database_connection):
    cursor = database_connection.cursor()
    cursor.execute("SELECT version_num FROM alembic_version;")
    assert cursor.fetchone()[0] == "20260825_0002"
    cursor.execute(
        """SELECT table_name FROM information_schema.tables
           WHERE table_schema = 'public';"""
    )
    tables = {row[0] for row in cursor.fetchall()}
    assert {
        "User", "Product", "Supplier", "Batch", "StockMovement",
        "PurchaseOrder", "PurchaseOrderItem", "GoodsReceipt",
        "GoodsReceiptItem", "PasswordReset", "Sale", "SaleItem",
        "SalesReturn", "SalesReturnItem",
    }.issubset(tables)
    cursor.close()


def test_database_rejects_negative_batch_stock(database_connection):
    cursor = database_connection.cursor()
    email = f"integration-{uuid.uuid4()}@example.com"
    try:
        cursor.execute(
            """INSERT INTO "User" (email, password_hash, full_name)
               VALUES (%s, 'test-hash', 'Integration User') RETURNING id;""",
            (email,),
        )
        owner_id = cursor.fetchone()[0]
        cursor.execute(
            """INSERT INTO "Product" (name, "ownerId")
               VALUES ('Constraint Test Product', %s) RETURNING id;""",
            (owner_id,),
        )
        product_id = cursor.fetchone()[0]
        cursor.execute("SAVEPOINT before_invalid_batch;")
        with pytest.raises(psycopg2.errors.CheckViolation):
            cursor.execute(
                """INSERT INTO "Batch" (
                       "batchNumber", "productId", quantity, "expiryDate", "ownerId"
                   ) VALUES ('NEGATIVE', %s, -1, CURRENT_DATE + 30, %s);""",
                (product_id, owner_id),
            )
        cursor.execute("ROLLBACK TO SAVEPOINT before_invalid_batch;")
    finally:
        database_connection.rollback()
        cursor.close()
