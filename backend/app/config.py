from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(slots=True)
class AppSettings:
    base_dir: Path
    data_dir: Path
    db_path: Path
    config_path: Path
    users_path: Path
    jwt_secret: str
    jwt_issuer: str
    jwt_access_token_ttl_minutes: int
    auto_start_simulator: bool
    default_locomotive_id: str
    cors_origins: list[str]
    realtime_websocket_url: str | None
    realtime_websocket_origin: str | None
    realtime_websocket_reconnect_seconds: int
    realtime_websocket_queue_size: int


@lru_cache
def get_settings() -> AppSettings:
    base_dir = Path(__file__).resolve().parents[1]
    data_dir = base_dir / "data"
    config_path = Path(os.getenv("DIGITAL_TWIN_CONFIG_PATH", base_dir / "app" / "settings.json"))
    users_path = Path(os.getenv("DIGITAL_TWIN_USERS_PATH", base_dir / "app" / "users.json"))
    db_path = Path(os.getenv("DIGITAL_TWIN_DB_PATH", data_dir / "telemetry.db"))
    raw_origins = os.getenv("DIGITAL_TWIN_CORS_ORIGINS", "*").strip()
    cors_origins = ["*"] if raw_origins == "*" else [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

    return AppSettings(
        base_dir=base_dir,
        data_dir=data_dir,
        db_path=db_path,
        config_path=config_path,
        users_path=users_path,
        jwt_secret=os.getenv("DIGITAL_TWIN_JWT_SECRET", "demo-jwt-secret-change-me"),
        jwt_issuer=os.getenv("DIGITAL_TWIN_JWT_ISSUER", "digital-twin-backend"),
        jwt_access_token_ttl_minutes=max(
            1,
            _as_int(os.getenv("DIGITAL_TWIN_JWT_ACCESS_TOKEN_TTL_MINUTES"), 60),
        ),
        auto_start_simulator=_as_bool(os.getenv("DIGITAL_TWIN_AUTO_START_SIMULATOR"), True),
        default_locomotive_id=os.getenv("DIGITAL_TWIN_DEFAULT_LOCOMOTIVE_ID", "locomotive-01"),
        cors_origins=cors_origins,
        realtime_websocket_url=(os.getenv("DIGITAL_TWIN_REALTIME_WS_URL") or "").strip() or None,
        realtime_websocket_origin=(os.getenv("DIGITAL_TWIN_REALTIME_WS_ORIGIN") or "").strip() or None,
        realtime_websocket_reconnect_seconds=max(
            1,
            _as_int(os.getenv("DIGITAL_TWIN_REALTIME_WS_RECONNECT_SECONDS"), 3),
        ),
        realtime_websocket_queue_size=max(
            1,
            _as_int(os.getenv("DIGITAL_TWIN_REALTIME_WS_QUEUE_SIZE"), 200),
        ),
    )


def load_health_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_health_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=2)
        file.write("\n")
