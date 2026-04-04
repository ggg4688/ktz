import importlib
import os
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient


class AuthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.db_path = Path(__file__).resolve().parents[1] / "data" / "test-auth.db"
        if cls.db_path.exists():
            cls.db_path.unlink()

        os.environ["DIGITAL_TWIN_AUTO_START_SIMULATOR"] = "false"
        os.environ["DIGITAL_TWIN_DB_PATH"] = str(cls.db_path)
        os.environ["DIGITAL_TWIN_JWT_SECRET"] = "test-suite-jwt-secret"
        os.environ["DIGITAL_TWIN_JWT_ISSUER"] = "digital-twin-test-suite"

        from app import config as config_module

        config_module.get_settings.cache_clear()
        import app.main as main_module

        cls.config_module = config_module
        cls.main_module = importlib.reload(main_module)
        cls.client_context = TestClient(cls.main_module.app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)
        cls.config_module.get_settings.cache_clear()
        if cls.db_path.exists():
            cls.db_path.unlink()

    def _login(self, username: str, password: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 200)
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_openapi_docs_are_available(self) -> None:
        docs_response = self.client.get("/docs")
        self.assertEqual(docs_response.status_code, 200)
        self.assertIn("Swagger UI", docs_response.text)

        openapi_response = self.client.get("/openapi.json")
        self.assertEqual(openapi_response.status_code, 200)
        self.assertEqual(openapi_response.json()["info"]["title"], "Locomotive Digital Twin Backend")

    def test_invalid_login_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401)

    def test_viewer_can_read_but_cannot_ingest(self) -> None:
        headers = self._login("viewer", "viewer123")

        me_response = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["role"], "viewer")

        overview_response = self.client.get("/api/v1/overview", headers=headers)
        self.assertEqual(overview_response.status_code, 200)

        ingest_response = self.client.post(
            "/api/v1/telemetry",
            headers=headers,
            json={
                "temperature_c": 84,
                "pressure_bar": 6.4,
                "fuel_level_pct": 68,
                "speed_kph": 86,
            },
        )
        self.assertEqual(ingest_response.status_code, 403)

    def test_operator_can_ingest(self) -> None:
        headers = self._login("operator", "operator123")

        ingest_response = self.client.post(
            "/api/v1/telemetry",
            headers=headers,
            json={
                "temperature_c": 84,
                "pressure_bar": 6.4,
                "fuel_level_pct": 68,
                "speed_kph": 86,
            },
        )

        self.assertEqual(ingest_response.status_code, 200)
        self.assertEqual(ingest_response.json()["health_category"], "normal")

    def test_metrics_and_config_update_require_admin(self) -> None:
        viewer_headers = self._login("viewer", "viewer123")
        admin_headers = self._login("admin", "admin123")

        viewer_metrics = self.client.get("/metrics", headers=viewer_headers)
        self.assertEqual(viewer_metrics.status_code, 403)

        admin_metrics = self.client.get("/metrics", headers=admin_headers)
        self.assertEqual(admin_metrics.status_code, 200)

        config_response = self.client.get("/api/v1/config/health-model", headers=admin_headers)
        self.assertEqual(config_response.status_code, 200)

        update_response = self.client.put(
            "/api/v1/config/health-model",
            headers=admin_headers,
            json=config_response.json(),
        )
        self.assertEqual(update_response.status_code, 200)

    def test_admin_can_create_user_and_new_user_can_login(self) -> None:
        admin_headers = self._login("admin", "admin123")

        create_response = self.client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "username": "dispatcher",
                "password": "dispatcher123",
                "full_name": "Route Dispatcher",
                "role": "viewer",
            },
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["username"], "dispatcher")
        self.assertEqual(create_response.json()["role"], "viewer")

        users_response = self.client.get("/api/v1/admin/users", headers=admin_headers)
        self.assertEqual(users_response.status_code, 200)
        self.assertTrue(any(item["username"] == "dispatcher" for item in users_response.json()))

        new_user_headers = self._login("dispatcher", "dispatcher123")
        me_response = self.client.get("/api/v1/auth/me", headers=new_user_headers)
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["full_name"], "Route Dispatcher")

    def test_non_admin_cannot_create_user(self) -> None:
        operator_headers = self._login("operator", "operator123")

        response = self.client.post(
            "/api/v1/admin/users",
            headers=operator_headers,
            json={
                "username": "auditor",
                "password": "auditor123",
                "role": "viewer",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_database_schema_and_seed_data_exist(self) -> None:
        headers = self._login("admin", "admin123")
        self.client.get("/api/v1/overview", headers=headers)

        with closing(sqlite3.connect(self.db_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            self.assertTrue(
                {
                    "users",
                    "locomotives",
                    "health_model_configs",
                    "telemetry_snapshots",
                    "alert_events",
                }.issubset(tables)
            )

            user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            active_configs = connection.execute(
                "SELECT COUNT(*) FROM health_model_configs WHERE is_active = 1"
            ).fetchone()[0]

        self.assertGreaterEqual(user_count, 3)
        self.assertEqual(active_configs, 1)


if __name__ == "__main__":
    unittest.main()
