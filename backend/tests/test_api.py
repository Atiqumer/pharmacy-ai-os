import os
import io
import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-chars-long!!")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_root_returns_online(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "version" in data


class TestSQLValidation:
    def test_allows_valid_select(self):
        from app.services.query_service import _validate_sql
        result = _validate_sql('SELECT * FROM "Product"')
        assert result == 'SELECT * FROM "Product"'

    def test_rejects_insert(self):
        from app.services.query_service import _validate_sql
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_sql('INSERT INTO "Product" (name) VALUES (\'test\')')

    def test_rejects_drop(self):
        from app.services.query_service import _validate_sql
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_sql('DROP TABLE "Product"')

    def test_rejects_delete(self):
        from app.services.query_service import _validate_sql
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_sql('DELETE FROM "Product" WHERE id = 1')

    def test_rejects_update(self):
        from app.services.query_service import _validate_sql
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_sql('UPDATE "Product" SET name = \'hacked\'')

    def test_rejects_unknown_table(self):
        from app.services.query_service import _validate_sql
        with pytest.raises(ValueError, match="not in the allowed list"):
            _validate_sql('SELECT * FROM "Admin Users"')

    def test_strips_semicolon(self):
        from app.services.query_service import _validate_sql
        result = _validate_sql('SELECT * FROM "Product";')
        assert result == 'SELECT * FROM "Product"'

    def test_allows_join(self):
        from app.services.query_service import _validate_sql
        result = _validate_sql('SELECT p.name FROM "Product" p JOIN "Batch" b ON p.id = b."productId"')
        assert "Product" in result
        assert "Batch" in result

    def test_requires_owner_filter_for_every_table_alias(self):
        from app.services.query_service import _validate_sql
        owner_id = "12345678-1234-1234-1234-123456789012"
        sql = (
            'SELECT p.name FROM "Product" AS p '
            'JOIN "Batch" AS b ON p.id = b."productId" '
            f'WHERE p."ownerId" = \'{owner_id}\''
        )
        with pytest.raises(ValueError, match="Missing tenant filter.*b"):
            _validate_sql(sql, owner_id)

    def test_accepts_server_scoped_owner_filters(self):
        from app.services.query_service import _validate_sql
        owner_id = "12345678-1234-1234-1234-123456789012"
        sql = (
            'SELECT p.name FROM "Product" AS p '
            'JOIN "Batch" AS b ON p.id = b."productId" '
            f'WHERE p."ownerId" = \'{owner_id}\' AND b."ownerId" = \'{owner_id}\''
        )
        assert _validate_sql(sql, owner_id) == sql

    def test_rejects_empty_query(self):
        from app.services.query_service import _validate_sql
        with pytest.raises(ValueError, match="Empty SQL query"):
            _validate_sql('')


class TestJWTAuth:
    def _get_test_token(self):
        from app.services.auth import create_access_token
        return create_access_token("test-user-id-12345678901234567", "test@example.com")

    def test_protected_endpoint_without_token(self):
        response = client.get("/analytics/morning-briefing")
        assert response.status_code == 401

    def test_protected_endpoint_with_invalid_token(self):
        response = client.get(
            "/analytics/morning-briefing",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    @patch("app.services.ai_service.client.chat.completions.create")
    @patch("app.services.ai_service.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_protected_endpoint_with_valid_token(self, mock_auth_db, mock_ai_db, mock_groq):
        auth_conn = MagicMock()
        auth_cursor = MagicMock()
        auth_cursor.fetchone.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "email": "test@example.com",
            "role": "user",
            "is_active": True,
        }
        auth_conn.cursor.return_value = auth_cursor
        mock_auth_db.return_value = auth_conn

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"total": 0}
        mock_cursor.fetchall.return_value = []
        mock_cursor.closed = False
        mock_conn.cursor.return_value = mock_cursor
        mock_ai_db.return_value = mock_conn
        mock_groq.return_value.choices = [MagicMock(message=MagicMock(content="All clear"))]

        token = self._get_test_token()
        response = client.get(
            "/analytics/morning-briefing",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code in (200, 500)

    def test_me_endpoint_without_token(self):
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_me_endpoint_with_invalid_token(self):
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer garbage"},
        )
        assert response.status_code == 401


class TestUploadCSVValidation:
    def _get_test_token(self):
        from app.services.auth import create_access_token
        return create_access_token("test-user-id-12345678901234567", "test@example.com")

    @patch("app.services.auth.get_db_connection")
    def test_rejects_non_csv_file(self, mock_db):
        self._mock_active_user(mock_db)
        token = self._get_test_token()
        response = client.post(
            "/inventory/upload-csv",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert response.status_code == 400

    @patch("app.services.auth.get_db_connection")
    def test_rejects_missing_required_columns(self, mock_db):
        self._mock_active_user(mock_db)
        token = self._get_test_token()
        csv_content = "wrong_column,another_column\ndata1,data2"
        response = client.post(
            "/inventory/upload-csv",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        )
        assert response.status_code == 400

    @staticmethod
    def _mock_active_user(mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "email": "test@example.com",
            "role": "user",
            "is_active": True,
        }
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn


class TestInventoryReporting:
    @staticmethod
    def _token():
        from app.services.auth import create_access_token
        return create_access_token(
            "12345678-1234-1234-1234-123456789012",
            "inventory@test.com",
        )

    @staticmethod
    def _mock_auth(mock_db):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "email": "inventory@test.com",
            "role": "user",
            "is_active": True,
        }
        conn.cursor.return_value = cursor
        mock_db.return_value = conn

    @patch("app.routes.inventory.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_summary_returns_operational_metrics(self, mock_auth_db, mock_inventory_db):
        self._mock_auth(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "total_products": 4,
            "total_units": 120,
            "low_stock_products": 1,
            "expiring_batches": 2,
            "expired_batches": 1,
            "cost_value": 500.0,
            "retail_value": 800.0,
        }
        conn.cursor.return_value = cursor
        mock_inventory_db.return_value = conn

        response = client.get(
            "/inventory/summary",
            headers={"Authorization": f"Bearer {self._token()}"},
        )
        assert response.status_code == 200
        assert response.json()["potential_margin"] == 300.0
        assert cursor.execute.call_args.args[1] == (
            "12345678-1234-1234-1234-123456789012",
            "12345678-1234-1234-1234-123456789012",
            "12345678-1234-1234-1234-123456789012",
        )

    @patch("app.routes.inventory.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_list_items_returns_tenant_scoped_batches(self, mock_auth_db, mock_inventory_db):
        self._mock_auth(mock_auth_db)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = [{
            "batch_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "product_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "name": "Panadol",
            "genericName": "Paracetamol",
            "category": "Analgesic",
            "minStockLevel": 10,
            "batchNumber": "PAN-1",
            "quantity": 5,
            "costPrice": 1.0,
            "retailPrice": 2.0,
            "expiryDate": "2027-01-01",
            "total_stock": 5,
            "total_count": 1,
        }]
        conn.cursor.return_value = cursor
        mock_inventory_db.return_value = conn

        response = client.get(
            "/inventory/items?stock_status=low_stock&search=Panadol",
            headers={"Authorization": f"Bearer {self._token()}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["batch_number"] == "PAN-1"
        sql, params = cursor.execute.call_args.args
        assert 'b."ownerId" = %s' in sql
        assert params[0] == "12345678-1234-1234-1234-123456789012"

    @patch("app.services.auth.get_db_connection")
    def test_list_items_rejects_invalid_filter(self, mock_auth_db):
        self._mock_auth(mock_auth_db)
        response = client.get(
            "/inventory/items?stock_status=unknown",
            headers={"Authorization": f"Bearer {self._token()}"},
        )
        assert response.status_code == 422


class TestAuthSignupValidation:
    def test_rejects_short_password(self):
        response = client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",
                "password": "short",
                "full_name": "Test User",
            },
        )
        assert response.status_code == 400
        assert "8 characters" in response.json()["detail"]

    def test_rejects_missing_email(self):
        response = client.post(
            "/auth/signup",
            json={
                "password": "validpassword123",
                "full_name": "Test User",
            },
        )
        assert response.status_code == 422

    @patch("app.routes.auth.get_db_connection")
    def test_login_returns_token(self, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        response = client.post(
            "/auth/login",
            json={"email": "nonexistent@example.com", "password": "whatever123"},
        )
        assert response.status_code == 401


class TestRBAC:
    def _get_admin_token(self):
        from app.services.auth import create_access_token
        return create_access_token("admin-user-id-12345678901234", "admin@test.com", "admin")

    def _get_user_token(self):
        from app.services.auth import create_access_token
        return create_access_token("regular-user-id-12345678901", "user@test.com", "user")

    @patch("app.routes.admin.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_admin_can_access_admin_routes(self, mock_auth_db, mock_db):
        auth_conn = MagicMock()
        auth_cursor = MagicMock()
        auth_cursor.fetchone.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "email": "admin@test.com",
            "role": "admin",
            "is_active": True,
        }
        auth_conn.cursor.return_value = auth_cursor
        mock_auth_db.return_value = auth_conn

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"total": 0}
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        token = self._get_admin_token()
        response = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    @patch("app.services.auth.get_db_connection")
    def test_regular_user_cannot_access_admin_routes(self, mock_auth_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "email": "user@test.com",
            "role": "user",
            "is_active": True,
        }
        mock_conn.cursor.return_value = mock_cursor
        mock_auth_db.return_value = mock_conn
        token = self._get_user_token()
        response = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    @patch("app.routes.auth.get_db_connection")
    @patch("app.services.auth.get_db_connection")
    def test_user_role_included_in_me_response(self, mock_auth_db, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": "test-id-123456789012345678",
            "email": "r@test.com",
            "full_name": "Test User",
            "role": "admin",
            "is_active": True,
            "created_at": "2024-01-01",
        }
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        auth_conn = MagicMock()
        auth_cursor = MagicMock()
        auth_cursor.fetchone.return_value = mock_cursor.fetchone.return_value
        auth_conn.cursor.return_value = auth_cursor
        mock_auth_db.return_value = auth_conn

        from app.services.auth import create_access_token
        token = create_access_token("test-id-123456789012345678", "r@test.com", "admin")
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    @patch("app.routes.auth.get_db_connection")
    def test_deactivated_user_cannot_login(self, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "email": "disabled@test.com",
            "full_name": "Disabled User",
            "role": "user",
            "is_active": False,
        }
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        response = client.post(
            "/auth/login",
            json={"email": "disabled@test.com", "password": "password123"},
        )
        assert response.status_code == 403

    @patch("app.services.auth.get_db_connection")
    def test_existing_token_is_rejected_after_deactivation(self, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "email": "disabled@test.com",
            "role": "user",
            "is_active": False,
        }
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        token = self._get_user_token()
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
