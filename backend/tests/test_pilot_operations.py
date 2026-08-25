import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-chars-long!!")

from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import create_access_token

client = TestClient(app)
OWNER_ID = "12345678-1234-1234-1234-123456789012"
PRODUCT_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
BATCH_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SALE_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"
SALE_ITEM_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"


def token():
    return create_access_token(OWNER_ID, "pilot@test.com")


def mock_auth(mock_db):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": OWNER_ID, "email": "pilot@test.com", "role": "user",
        "is_active": True, "token_valid_after": None,
    }
    conn.cursor.return_value = cursor
    mock_db.return_value = conn


class TestPilotSales:
    @patch("app.routes.sales.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_sale_allocates_earliest_expiry_and_records_movement(self, mock_auth_db, mock_sales_db):
        mock_auth(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"id": PRODUCT_ID, "name": "Panadol"},
            {"id": SALE_ID, "saleNumber": "SALE-TEST", "status": "completed", "created_at": "2026-08-25"},
        ]
        cursor.fetchall.return_value = [{
            "id": BATCH_ID, "quantity": 5, "retailPrice": Decimal("15"),
            "costPrice": Decimal("10"), "expiryDate": "2027-01-01",
        }]
        conn.cursor.return_value = cursor
        mock_sales_db.return_value = conn

        response = client.post(
            "/sales",
            headers={"Authorization": f"Bearer {token()}"},
            json={"items": [{"product_id": PRODUCT_ID, "quantity": 3}], "discount": 5},
        )

        assert response.status_code == 201
        assert response.json()["total"] == 40.0
        assert any(
            'UPDATE "Batch" SET quantity' in call.args[0] and call.args[1][0] == 2
            for call in cursor.execute.call_args_list
        )
        assert any(
            'INSERT INTO "StockMovement"' in call.args[0] and call.args[1][4] == -3
            for call in cursor.execute.call_args_list
        )
        conn.commit.assert_called_once()

    @patch("app.routes.sales.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_sale_rejects_insufficient_non_expired_stock(self, mock_auth_db, mock_sales_db):
        mock_auth(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {"id": PRODUCT_ID, "name": "Panadol"}
        cursor.fetchall.return_value = [{
            "id": BATCH_ID, "quantity": 1, "retailPrice": Decimal("15"),
            "costPrice": Decimal("10"), "expiryDate": "2027-01-01",
        }]
        conn.cursor.return_value = cursor
        mock_sales_db.return_value = conn

        response = client.post(
            "/sales",
            headers={"Authorization": f"Bearer {token()}"},
            json={"items": [{"product_id": PRODUCT_ID, "quantity": 2}]},
        )

        assert response.status_code == 409
        assert "Available: 1" in response.json()["detail"]
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()

    @patch("app.routes.sales.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_return_restores_original_batch_and_audit_movement(self, mock_auth_db, mock_sales_db):
        mock_auth(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"id": SALE_ID, "saleNumber": "SALE-TEST", "subtotal": Decimal("45"), "discount": Decimal("0"), "total": Decimal("45")},
            {"id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee", "returnNumber": "RET-TEST", "created_at": "2026-08-25"},
            {"fully_returned": True},
        ]
        cursor.fetchall.return_value = [{
            "id": SALE_ITEM_ID, "saleId": SALE_ID, "productId": PRODUCT_ID,
            "batchId": BATCH_ID, "quantity": 3, "returnedQuantity": 0,
            "unitPrice": Decimal("15"), "batch_quantity": 2,
        }]
        conn.cursor.return_value = cursor
        mock_sales_db.return_value = conn

        response = client.post(
            f"/sales/{SALE_ID}/returns",
            headers={"Authorization": f"Bearer {token()}"},
            json={"reason": "Customer returned sealed pack", "items": [{"sale_item_id": SALE_ITEM_ID, "quantity": 3}]},
        )

        assert response.status_code == 201
        assert response.json()["sale_status"] == "refunded"
        assert response.json()["refund_amount"] == 45.0
        assert any(
            'UPDATE "Batch" SET quantity' in call.args[0] and call.args[1][0] == 5
            for call in cursor.execute.call_args_list
        )
        assert any(
            'INSERT INTO "StockMovement"' in call.args[0] and call.args[1][4] == 3
            for call in cursor.execute.call_args_list
        )


class TestPilotInventoryLifecycle:
    @patch("app.routes.inventory.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_product_details_can_be_updated_without_changing_stock(self, mock_auth_db, mock_inventory_db):
        mock_auth(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"id": PRODUCT_ID, "is_active": True},
            {
                "id": PRODUCT_ID, "name": "Panadol 500mg", "genericName": "Paracetamol",
                "category": "Analgesic", "minStockLevel": 12, "sku": "PAN-500",
                "barcode": "123456", "manufacturer": "Test Pharma", "strength": "500mg",
                "dosage_form": "Tablet", "is_active": True, "updated_at": "2026-08-25",
            },
        ]
        conn.cursor.return_value = cursor
        mock_inventory_db.return_value = conn

        response = client.patch(
            f"/inventory/products/{PRODUCT_ID}",
            headers={"Authorization": f"Bearer {token()}"},
            json={
                "name": "Panadol 500mg", "generic_name": "Paracetamol", "category": "Analgesic",
                "min_stock_level": 12, "sku": "PAN-500", "barcode": "123456",
                "manufacturer": "Test Pharma", "strength": "500mg", "dosage_form": "Tablet",
            },
        )

        assert response.status_code == 200
        assert response.json()["sku"] == "PAN-500"
        assert all('quantity =' not in call.args[0] for call in cursor.execute.call_args_list)
        conn.commit.assert_called_once()

    @patch("app.routes.inventory.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_product_with_stock_cannot_be_archived(self, mock_auth_db, mock_inventory_db):
        mock_auth(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {"id": PRODUCT_ID, "is_active": True, "stock": 4}
        conn.cursor.return_value = cursor
        mock_inventory_db.return_value = conn

        response = client.patch(
            f"/inventory/products/{PRODUCT_ID}",
            headers={"Authorization": f"Bearer {token()}"},
            json={"is_active": False},
        )

        assert response.status_code == 409
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()

    @patch("app.routes.inventory.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_batch_prices_and_expiry_can_be_updated_without_stock_change(self, mock_auth_db, mock_inventory_db):
        mock_auth(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"id": BATCH_ID, "quantity": 4},
            {
                "id": BATCH_ID, "batchNumber": "PAN-UPDATED", "supplierId": None,
                "costPrice": Decimal("11"), "retailPrice": Decimal("16"),
                "expiryDate": "2028-01-01", "quantity": 4, "is_active": True,
                "updated_at": "2026-08-25",
            },
        ]
        conn.cursor.return_value = cursor
        mock_inventory_db.return_value = conn

        response = client.patch(
            f"/inventory/items/{BATCH_ID}",
            headers={"Authorization": f"Bearer {token()}"},
            json={"batch_number": "PAN-UPDATED", "cost_price": 11, "retail_price": 16, "expiry_date": "2028-01-01"},
        )

        assert response.status_code == 200
        assert response.json()["quantity"] == 4
        update_sql = cursor.execute.call_args_list[-1].args[0]
        assert '"costPrice" = %s' in update_sql
        assert "quantity = %s" not in update_sql


class TestPilotPurchasing:
    @patch("app.routes.purchasing.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_unreceived_order_can_be_cancelled(self, mock_auth_db, mock_purchasing_db):
        mock_auth(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {"orderNumber": "PO-TEST"}
        conn.cursor.return_value = cursor
        mock_purchasing_db.return_value = conn

        response = client.post(
            "/purchasing/orders/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/cancel",
            headers={"Authorization": f"Bearer {token()}"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        sql = cursor.execute.call_args.args[0]
        assert "receivedQuantity" in sql
        conn.commit.assert_called_once()


class TestPilotReports:
    @patch("app.routes.reports.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_summary_reports_net_sales_after_refunds(self, mock_auth_db, mock_reports_db):
        mock_auth(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"sale_count": 2, "sales_total": Decimal("100"), "discounts": Decimal("5")},
            {"cost_of_goods": Decimal("50"), "gross_item_revenue": Decimal("90"), "gross_returned_value": Decimal("10")},
            {"refunds": Decimal("10")},
            {"open_orders": 1, "open_order_value": Decimal("40")},
        ]
        conn.cursor.return_value = cursor
        mock_reports_db.return_value = conn

        response = client.get(
            "/reports/summary?date_from=2026-08-01&date_to=2026-08-31",
            headers={"Authorization": f"Bearer {token()}"},
        )

        assert response.status_code == 200
        assert response.json()["sales_total"] == 90.0
        assert response.json()["estimated_gross_profit"] == 40.0
