from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import query_service


OWNER_ID = "12345678-1234-1234-1234-123456789012"


@pytest.mark.parametrize(
    "question",
    [
        "show medicines running low",
        "list low stock products",
        "what needs reorder",
        "show products below the minimum",
    ],
)
def test_common_low_stock_phrases_use_trusted_query(question):
    sql = query_service._deterministic_query(question, OWNER_ID)

    assert 'COALESCE(SUM(b.quantity), 0) <= p."minStockLevel"' in sql
    assert f'p."ownerId" = \'{OWNER_ID}\'' in sql
    assert f'b."ownerId" = \'{OWNER_ID}\'' in sql
    assert "LIMIT 100" in sql


def test_out_of_stock_is_not_misclassified_as_general_low_stock():
    sql = query_service._deterministic_query("show out of stock medicines", OWNER_ID)

    assert "COALESCE(SUM(b.quantity), 0) <= 0" in sql
    assert 'p."minStockLevel"' in sql


def test_expired_and_expiring_queries_use_distinct_date_windows():
    expired_sql = query_service._deterministic_query("show expired batches", OWNER_ID)
    expiring_sql = query_service._deterministic_query("what expires in 30 days", OWNER_ID)

    assert 'b."expiryDate" < CURRENT_DATE' in expired_sql
    assert "BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'" in expiring_sql


def test_expiring_query_defaults_to_90_days_and_caps_large_windows():
    default_sql = query_service._deterministic_query("show near expiry stock", OWNER_ID)
    capped_sql = query_service._deterministic_query("show items expiring in 999 days", OWNER_ID)

    assert "INTERVAL '90 days'" in default_sql
    assert "INTERVAL '365 days'" in capped_sql


def test_deterministic_intent_bypasses_groq_and_executes_read_only():
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchmany.return_value = [{"product_name": "Test", "total_quantity": 2}]
    connection.cursor.return_value = cursor

    with patch.object(query_service, "get_db_connection", return_value=connection), patch.object(
        query_service, "get_groq_client"
    ) as groq:
        result = query_service.execute_natural_query("show medicines running low", OWNER_ID)

    assert result["status"] == "success"
    assert result["data"] == [{"product_name": "Test", "total_quantity": 2}]
    groq.assert_not_called()
    assert cursor.execute.call_args_list[0].args[0] == "SET TRANSACTION READ ONLY"
    assert cursor.execute.call_args_list[1].args[0] == "SET LOCAL statement_timeout = '5s'"
    connection.rollback.assert_called_once()
    cursor.close.assert_called_once()
    connection.close.assert_called_once()


def test_provider_failure_is_reported_before_database_access():
    error = RuntimeError("Invalid API key gsk_do-not-expose")
    error.status_code = 401
    client = MagicMock()
    client.chat.completions.create.side_effect = error

    with patch.object(query_service, "get_groq_client", return_value=client), patch.object(
        query_service, "get_db_connection"
    ) as database:
        result = query_service.execute_natural_query("find a product called Test", OWNER_ID)

    assert result["status"] == "error"
    assert "Replace GROQ_API_KEY" in result["detail"]
    assert "gsk_do-not-expose" not in result["detail"]
    database.assert_not_called()


def test_database_failure_is_not_misreported_as_a_provider_failure():
    sql = (
        'SELECT p.name FROM "Product" AS p '
        f'WHERE p."ownerId" = \'{OWNER_ID}\' LIMIT 100'
    )
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=sql))]
    )
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    connection = MagicMock()
    cursor = MagicMock()
    cursor.execute.side_effect = [None, None, RuntimeError("database failure")]
    connection.cursor.return_value = cursor

    with patch.object(query_service, "get_groq_client", return_value=client), patch.object(
        query_service, "get_db_connection", return_value=connection
    ):
        result = query_service.execute_natural_query("find a product called Test", OWNER_ID)

    assert result == {
        "status": "error",
        "detail": "The generated inventory query could not be executed. Try rephrasing the request.",
    }
    connection.rollback.assert_called_once()
    cursor.close.assert_called_once()
    connection.close.assert_called_once()
