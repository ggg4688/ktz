from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import AppSettings, load_health_config
from app.models import AlertItem, FactorContribution, RecommendationItem, TelemetrySnapshot


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SnapshotRepository:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._db_path = settings.db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self._db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row

        with self._lock:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = NORMAL")
            self._initialize_schema()
            self._seed_reference_data()

    def get_user(self, username: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT username, full_name, role, salt, password_hash, iterations, disabled
                FROM users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_users(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT username, full_name, role, salt, password_hash, iterations, disabled
                FROM users
                ORDER BY username ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_user(
        self,
        username: str,
        full_name: str,
        role: str,
        salt: str,
        password_hash: str,
        iterations: int,
        disabled: bool = False,
    ) -> dict[str, Any]:
        timestamp = utc_now().isoformat()

        with self._lock:
            try:
                self._connection.execute(
                    """
                    INSERT INTO users (
                        username,
                        full_name,
                        role,
                        salt,
                        password_hash,
                        iterations,
                        disabled,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        username,
                        full_name,
                        role,
                        salt,
                        password_hash,
                        iterations,
                        1 if disabled else 0,
                        timestamp,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                if "users.username" in str(exc):
                    raise ValueError("User already exists") from exc
                raise

            self._connection.commit()

        created_user = self.get_user(username)
        if created_user is None:
            raise RuntimeError("User insert succeeded but the user could not be loaded")
        return created_user

    def get_active_health_config(self) -> tuple[int, dict[str, Any]]:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT version, config_json
                FROM health_model_configs
                WHERE is_active = 1
                ORDER BY version DESC
                LIMIT 1
                """
            ).fetchone()

        if row is None:
            raise RuntimeError("No active health model configuration is stored in the database")

        return int(row["version"]), json.loads(row["config_json"])

    def set_active_health_config(
        self,
        new_config: dict[str, Any],
        created_by: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        config_payload = {
            key: value
            for key, value in new_config.items()
            if key not in {"health_model_version", "created_at", "created_by", "is_active"}
        }
        created_at = utc_now().isoformat()

        with self._lock:
            version = int(
                self._connection.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 FROM health_model_configs"
                ).fetchone()[0]
            )
            self._connection.execute("UPDATE health_model_configs SET is_active = 0 WHERE is_active = 1")
            self._connection.execute(
                """
                INSERT INTO health_model_configs (
                    version,
                    is_active,
                    config_json,
                    created_at,
                    created_by
                ) VALUES (?, 1, ?, ?, ?)
                """,
                (version, json.dumps(config_payload), created_at, created_by),
            )
            self._connection.commit()

        return version, config_payload

    def insert_snapshot(self, snapshot: TelemetrySnapshot, health_model_version: int) -> TelemetrySnapshot:
        created_at = utc_now().isoformat()
        captured_at = snapshot.captured_at.isoformat()

        with self._lock:
            self._ensure_locomotive(snapshot.locomotive_id)
            cursor = self._connection.execute(
                """
                INSERT INTO telemetry_snapshots (
                    locomotive_id,
                    captured_at,
                    distance_km,
                    scenario_tag,
                    temperature_c,
                    pressure_bar,
                    fuel_level_pct,
                    speed_kph,
                    smoothed_temperature_c,
                    smoothed_pressure_bar,
                    smoothed_fuel_level_pct,
                    smoothed_speed_kph,
                    health_score,
                    health_category,
                    alert_penalty,
                    formula,
                    top_factors_json,
                    alerts_json,
                    recommendations_json,
                    created_at,
                    health_model_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.locomotive_id,
                    captured_at,
                    snapshot.distance_km,
                    snapshot.scenario_tag,
                    snapshot.temperature_c,
                    snapshot.pressure_bar,
                    snapshot.fuel_level_pct,
                    snapshot.speed_kph,
                    snapshot.smoothed_temperature_c,
                    snapshot.smoothed_pressure_bar,
                    snapshot.smoothed_fuel_level_pct,
                    snapshot.smoothed_speed_kph,
                    snapshot.health_score,
                    snapshot.health_category,
                    snapshot.alert_penalty,
                    snapshot.formula,
                    json.dumps([item.model_dump(mode="json") for item in snapshot.top_factors]),
                    json.dumps([item.model_dump(mode="json") for item in snapshot.alerts]),
                    json.dumps([item.model_dump(mode="json") for item in snapshot.recommendations]),
                    created_at,
                    health_model_version,
                ),
            )
            sequence_id = int(cursor.lastrowid)
            if snapshot.alerts:
                self._connection.executemany(
                    """
                    INSERT INTO alert_events (
                        snapshot_id,
                        locomotive_id,
                        captured_at,
                        code,
                        severity,
                        metric,
                        message,
                        recommendation,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            sequence_id,
                            snapshot.locomotive_id,
                            captured_at,
                            alert.code,
                            alert.severity,
                            alert.metric,
                            alert.message,
                            alert.recommendation,
                            created_at,
                        )
                        for alert in snapshot.alerts
                    ],
                )
            self._connection.commit()

        return snapshot.model_copy(update={"sequence_id": sequence_id})

    def get_latest_snapshot(self, locomotive_id: str) -> TelemetrySnapshot | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT *
                FROM telemetry_snapshots
                WHERE locomotive_id = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT 1
                """,
                (locomotive_id,),
            ).fetchone()
        return self._row_to_snapshot(row) if row is not None else None

    def get_snapshots_since(
        self,
        locomotive_id: str,
        since: datetime,
        limit: int,
    ) -> list[TelemetrySnapshot]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM telemetry_snapshots
                WHERE locomotive_id = ?
                  AND captured_at >= ?
                ORDER BY captured_at ASC, id ASC
                LIMIT ?
                """,
                (locomotive_id, since.isoformat(), limit),
            ).fetchall()
        return [self._row_to_snapshot(row) for row in rows]

    def prune_older_than(self, retention_hours: int) -> int:
        cutoff = (utc_now() - timedelta(hours=retention_hours)).isoformat()
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM telemetry_snapshots WHERE captured_at < ?",
                (cutoff,),
            )
            self._connection.commit()
        return int(cursor.rowcount or 0)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _initialize_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                iterations INTEGER NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS locomotives (
                locomotive_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS health_model_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 0,
                config_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT
            )
            """
        )
        self._connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_health_model_configs_active
            ON health_model_configs(is_active)
            WHERE is_active = 1
            """
        )
        self._ensure_telemetry_snapshots_table()
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                locomotive_id TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                code TEXT NOT NULL,
                severity TEXT NOT NULL,
                metric TEXT NOT NULL,
                message TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(snapshot_id) REFERENCES telemetry_snapshots(id) ON DELETE CASCADE
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_telemetry_snapshots_locomotive_captured_at
            ON telemetry_snapshots(locomotive_id, captured_at DESC, id DESC)
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_alert_events_locomotive_captured_at
            ON alert_events(locomotive_id, captured_at DESC, id DESC)
            """
        )
        self._connection.commit()

    def _ensure_telemetry_snapshots_table(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                locomotive_id TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                distance_km REAL,
                scenario_tag TEXT,
                temperature_c REAL NOT NULL,
                pressure_bar REAL NOT NULL,
                fuel_level_pct REAL NOT NULL,
                speed_kph REAL NOT NULL,
                smoothed_temperature_c REAL NOT NULL,
                smoothed_pressure_bar REAL NOT NULL,
                smoothed_fuel_level_pct REAL NOT NULL,
                smoothed_speed_kph REAL NOT NULL,
                health_score REAL NOT NULL,
                health_category TEXT NOT NULL,
                alert_penalty REAL NOT NULL,
                formula TEXT NOT NULL,
                top_factors_json TEXT NOT NULL,
                alerts_json TEXT NOT NULL,
                recommendations_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                health_model_version INTEGER
            )
            """
        )
        columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(telemetry_snapshots)").fetchall()
        }
        if "health_model_version" not in columns:
            self._connection.execute(
                "ALTER TABLE telemetry_snapshots ADD COLUMN health_model_version INTEGER"
            )

    def _seed_reference_data(self) -> None:
        if self._count_rows("users") == 0:
            self._seed_users()

        self._ensure_locomotive(self._settings.default_locomotive_id)

        try:
            version, _ = self.get_active_health_config()
        except RuntimeError:
            version, _ = self.set_active_health_config(load_health_config(self._settings.config_path))

        with self._lock:
            self._connection.execute(
                """
                UPDATE telemetry_snapshots
                SET health_model_version = ?
                WHERE health_model_version IS NULL
                """,
                (version,),
            )
            self._connection.commit()

    def _seed_users(self) -> None:
        with self._settings.users_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        raw_users = payload["users"] if isinstance(payload, dict) else payload
        created_at = utc_now().isoformat()
        self._connection.executemany(
            """
            INSERT INTO users (
                username,
                full_name,
                role,
                salt,
                password_hash,
                iterations,
                disabled,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    raw_user["username"],
                    raw_user.get("full_name", raw_user["username"]),
                    raw_user["role"],
                    raw_user["salt"],
                    raw_user["password_hash"],
                    int(raw_user.get("iterations", 120_000)),
                    1 if raw_user.get("disabled", False) else 0,
                    created_at,
                    created_at,
                )
                for raw_user in raw_users
            ],
        )
        self._connection.commit()

    def _ensure_locomotive(self, locomotive_id: str) -> None:
        self._connection.execute(
            """
            INSERT OR IGNORE INTO locomotives (locomotive_id, display_name, created_at)
            VALUES (?, ?, ?)
            """,
            (
                locomotive_id,
                locomotive_id.replace("-", " ").title(),
                utc_now().isoformat(),
            ),
        )

    def _count_rows(self, table_name: str) -> int:
        return int(self._connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> TelemetrySnapshot:
        return TelemetrySnapshot(
            sequence_id=int(row["id"]),
            locomotive_id=row["locomotive_id"],
            captured_at=datetime.fromisoformat(row["captured_at"]),
            distance_km=row["distance_km"],
            scenario_tag=row["scenario_tag"],
            temperature_c=float(row["temperature_c"]),
            pressure_bar=float(row["pressure_bar"]),
            fuel_level_pct=float(row["fuel_level_pct"]),
            speed_kph=float(row["speed_kph"]),
            smoothed_temperature_c=float(row["smoothed_temperature_c"]),
            smoothed_pressure_bar=float(row["smoothed_pressure_bar"]),
            smoothed_fuel_level_pct=float(row["smoothed_fuel_level_pct"]),
            smoothed_speed_kph=float(row["smoothed_speed_kph"]),
            health_score=float(row["health_score"]),
            health_category=row["health_category"],
            alert_penalty=float(row["alert_penalty"]),
            formula=row["formula"],
            top_factors=[
                FactorContribution.model_validate(item)
                for item in json.loads(row["top_factors_json"] or "[]")
            ],
            alerts=[AlertItem.model_validate(item) for item in json.loads(row["alerts_json"] or "[]")],
            recommendations=[
                RecommendationItem.model_validate(item)
                for item in json.loads(row["recommendations_json"] or "[]")
            ],
        )
