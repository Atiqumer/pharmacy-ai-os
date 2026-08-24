import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-chars-long!!")

from fastapi.testclient import TestClient
from app.main import app
from app.services.auth import create_access_token

client = TestClient(app)
OWNER_ID = "12345678-1234-1234-1234-123456789012"
SUPPLIER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PRODUCT_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ORDER_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"
ORDER_ITEM_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"
BATCH_ID = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"


def token():
    return create_access_token(OWNER_ID, "purchasing@test.com")


def mock_active_user(mock_db):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": OWNER_ID,
        "email": "purchasing@test.com",
        "role": "user",
        "is_active": True,
    }
    conn.cursor.return_value = cursor
    mock_db.return_value = conn


def auth_headers():
    return {"Authorization": f"Bearer {token()}"}


class TestSuppliers:
    @patch("app.routes.suppliers.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_supplier_list_is_owner_scoped(self, mock_auth_db, mock_supplier_db):
        mock_active_user(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_supplier_db.return_value = conn

        response = client.get("/suppliers", headers=auth_headers())
        assert response.status_code == 200
        sql, params = cursor.execute.call_args.args
        assert '"ownerId" = %s' in sql
        assert params[0] == OWNER_ID

    @patch("app.routes.suppliers.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_create_supplier(self, mock_auth_db, mock_supplier_db):
        mock_active_user(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "id": SUPPLIER_ID,
            "name": "Health Distributors",
            "contact_name": "Ali",
            "phone": "03001234567",
            "email": "ali@example.com",
            "address": "Karachi",
            "is_active": True,
            "created_at": "2026-08-25T10:00:00",
        }
        conn.cursor.return_value = cursor
        mock_supplier_db.return_value = conn

        response = client.post(
            "/suppliers",
            headers=auth_headers(),
            json={"name": "Health Distributors", "contact_name": "Ali", "email": "ali@example.com"},
        )
        assert response.status_code == 201
        assert response.json()["id"] == SUPPLIER_ID
        conn.commit.assert_called_once()


class TestPurchasing:
    @patch("app.routes.purchasing.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_create_purchase_order_validates_owned_products(self, mock_auth_db, mock_purchasing_db):
        mock_active_user(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {"id": SUPPLIER_ID}
        cursor.fetchall.return_value = []
        conn.cursor.return_value = cursor
        mock_purchasing_db.return_value = conn

        response = client.post(
            "/purchasing/orders",
            headers=auth_headers(),
            json={
                "supplier_id": SUPPLIER_ID,
                "items": [{"product_id": PRODUCT_ID, "quantity": 10, "cost_price": "5.00"}],
            },
        )
        assert response.status_code == 400
        assert "do not belong" in response.json()["detail"]
        conn.rollback.assert_called_once()

    @patch("app.routes.purchasing.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_submit_draft_purchase_order(self, mock_auth_db, mock_purchasing_db):
        mock_active_user(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {"orderNumber": "PO-20260825-ABC123"}
        conn.cursor.return_value = cursor
        mock_purchasing_db.return_value = conn

        response = client.post(
            f"/purchasing/orders/{ORDER_ID}/submit",
            headers=auth_headers(),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ordered"
        conn.commit.assert_called_once()

    @patch("app.routes.purchasing.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_receiving_posts_batch_and_stock_movement_atomically(self, mock_auth_db, mock_purchasing_db):
        mock_active_user(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"id": ORDER_ID, "supplierId": SUPPLIER_ID, "orderNumber": "PO-1", "status": "ordered"},
            {"id": "ffffffff-ffff-ffff-ffff-ffffffffffff", "received_at": "2026-08-25T10:00:00"},
            {"id": BATCH_ID, "quantity": 4},
            {"complete": True},
        ]
        cursor.fetchall.return_value = [{
            "id": ORDER_ITEM_ID,
            "productId": PRODUCT_ID,
            "orderedQuantity": 10,
            "receivedQuantity": 0,
            "costPrice": 5,
        }]
        conn.cursor.return_value = cursor
        mock_purchasing_db.return_value = conn

        response = client.post(
            f"/purchasing/orders/{ORDER_ID}/receive",
            headers=auth_headers(),
            json={
                "reference": "INV-100",
                "items": [{
                    "purchase_order_item_id": ORDER_ITEM_ID,
                    "quantity": 10,
                    "batch_number": "B-100",
                    "expiry_date": "2027-12-01",
                    "retail_price": "8.00",
                }],
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "received"
        assert any('INSERT INTO "StockMovement"' in call.args[0] for call in cursor.execute.call_args_list)
        assert any('INSERT INTO "GoodsReceiptItem"' in call.args[0] for call in cursor.execute.call_args_list)
        conn.commit.assert_called_once()

    @patch("app.routes.purchasing.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_receiving_rejects_quantity_above_order_balance(self, mock_auth_db, mock_purchasing_db):
        mock_active_user(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "id": ORDER_ID, "supplierId": SUPPLIER_ID,
            "orderNumber": "PO-1", "status": "partially_received",
        }
        cursor.fetchall.return_value = [{
            "id": ORDER_ITEM_ID,
            "productId": PRODUCT_ID,
            "orderedQuantity": 10,
            "receivedQuantity": 8,
            "costPrice": 5,
        }]
        conn.cursor.return_value = cursor
        mock_purchasing_db.return_value = conn

        response = client.post(
            f"/purchasing/orders/{ORDER_ID}/receive",
            headers=auth_headers(),
            json={
                "items": [{
                    "purchase_order_item_id": ORDER_ITEM_ID,
                    "quantity": 3,
                    "batch_number": "B-100",
                    "expiry_date": "2027-12-01",
                    "retail_price": "8.00",
                }],
            },
        )
        assert response.status_code == 409
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()
