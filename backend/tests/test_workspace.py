import os
from datetime import date, datetime
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-chars-long!!")

from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import create_access_token


client = TestClient(app)
OWNER_ID = "12345678-1234-1234-1234-123456789012"


def _headers():
    return {"Authorization": f"Bearer {create_access_token(OWNER_ID, 'owner@example.com')}"}


def _active_auth_connection():
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": OWNER_ID,
        "email": "owner@example.com",
        "role": "user",
        "is_active": True,
    }
    connection.cursor.return_value = cursor
    return connection


def _workspace_connection():
    connection = MagicMock()
    cursor = MagicMock()
    cursor.closed = False
    connection.cursor.return_value = cursor
    return connection, cursor


class TestPharmacySetup:
    @patch("app.routes.workspace.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_new_account_requires_setup(self, mock_auth_db, mock_workspace_db):
        mock_auth_db.return_value = _active_auth_connection()
        connection, cursor = _workspace_connection()
        cursor.fetchone.return_value = None
        mock_workspace_db.return_value = connection

        response = client.get("/settings/pharmacy", headers=_headers())

        assert response.status_code == 200
        assert response.json()["setup_complete"] is False
        assert response.json()["profile"]["expiry_alert_days"] == 90

    @patch("app.routes.workspace.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_profile_can_be_created_and_normalized(self, mock_auth_db, mock_workspace_db):
        mock_auth_db.return_value = _active_auth_connection()
        connection, cursor = _workspace_connection()
        cursor.fetchone.return_value = {
            "name": "City Pharmacy",
            "phone": None,
            "address": "Main Road",
            "expiry_alert_days": 60,
            "low_stock_alerts": True,
            "expiry_alerts": True,
            "onboarding_completed_at": datetime(2026, 8, 26, 10, 0),
            "updated_at": datetime(2026, 8, 26, 10, 0),
        }
        mock_workspace_db.return_value = connection

        response = client.put(
            "/settings/pharmacy",
            headers=_headers(),
            json={
                "name": "  City Pharmacy  ",
                "phone": "",
                "address": " Main Road ",
                "expiry_alert_days": 60,
                "low_stock_alerts": True,
                "expiry_alerts": True,
            },
        )

        assert response.status_code == 200
        assert response.json()["setup_complete"] is True
        assert response.json()["profile"]["name"] == "City Pharmacy"
        assert connection.commit.called
        parameters = cursor.execute.call_args.args[1]
        assert parameters[1] == "City Pharmacy"
        assert parameters[2] is None

    @patch("app.routes.workspace.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_profile_rejects_invalid_expiry_window(self, mock_auth_db, mock_workspace_db):
        mock_auth_db.return_value = _active_auth_connection()

        response = client.put(
            "/settings/pharmacy",
            headers=_headers(),
            json={"name": "City Pharmacy", "expiry_alert_days": 500},
        )

        assert response.status_code == 422
        mock_workspace_db.assert_not_called()


class TestInventoryNotifications:
    @patch("app.routes.workspace.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_low_stock_and_expiry_alerts_are_owner_scoped(self, mock_auth_db, mock_workspace_db):
        mock_auth_db.return_value = _active_auth_connection()
        connection, cursor = _workspace_connection()
        cursor.fetchone.return_value = {
            "expiry_alert_days": 90,
            "low_stock_alerts": True,
            "expiry_alerts": True,
        }
        cursor.fetchall.side_effect = [
            [{
                "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "name": "Paracetamol",
                "minStockLevel": 10,
                "stock": 3,
            }],
            [{
                "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "productId": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "batchNumber": "B-001",
                "quantity": 4,
                "expiryDate": date(2026, 8, 30),
                "name": "Paracetamol",
                "days_remaining": 4,
            }],
        ]
        mock_workspace_db.return_value = connection

        response = client.get("/notifications", headers=_headers())

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert {item["type"] for item in data["notifications"]} == {"low_stock", "expiry"}
        assert all(OWNER_ID in call.args[1] for call in cursor.execute.call_args_list)

    @patch("app.routes.workspace.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_disabled_alert_types_do_not_query_inventory(self, mock_auth_db, mock_workspace_db):
        mock_auth_db.return_value = _active_auth_connection()
        connection, cursor = _workspace_connection()
        cursor.fetchone.return_value = {
            "expiry_alert_days": 90,
            "low_stock_alerts": False,
            "expiry_alerts": False,
        }
        mock_workspace_db.return_value = connection

        response = client.get("/notifications", headers=_headers())

        assert response.status_code == 200
        assert response.json()["notifications"] == []
        assert cursor.execute.call_count == 1
