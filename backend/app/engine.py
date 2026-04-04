from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import dataclass
from datetime import timedelta
from io import StringIO
from typing import Any

from app.config import AppSettings
from app.models import AlertSnapshot, TelemetryIn, TelemetrySnapshot
from app.repository import SnapshotRepository, utc_now
from app.scoring import METRIC_FIELDS, calculate_health, describe_formula, validate_health_config


@dataclass(slots=True)
class ServiceMetrics:
    ingested_total: int = 0
    simulator_generated_total: int = 0
    external_ingested_total: int = 0
    duplicate_events_total: int = 0
    active_alerts_observed_total: int = 0
    last_ingested_at: str | None = None


class EventBroker:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[str]] = set()

    async def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self._queues.discard(queue)

    def publish(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, default=str)
        for queue in list(self._queues):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(encoded)
            except asyncio.QueueFull:
                continue

    @property
    def subscriber_count(self) -> int:
        return len(self._queues)


class TelemetryEngine:
    def __init__(self, settings: AppSettings, repository: SnapshotRepository, broker: EventBroker) -> None:
        self.settings = settings
        self.repository = repository
        self.broker = broker
        self.metrics = ServiceMetrics()
        self._health_config_version, self._health_config = repository.get_active_health_config()
        self._formula_details = self._compose_formula_details()
        self._latest_snapshots: dict[str, TelemetrySnapshot] = {}
        self._smoothed_values: dict[str, dict[str, float]] = {}
        self._last_signatures: dict[str, tuple[str, tuple[float, ...]]] = {}
        self._samples_since_prune = 0

    def ingest(self, payload: TelemetryIn, source: str = "external") -> TelemetrySnapshot:
        captured_at = payload.captured_at or utc_now()
        signature = (
            captured_at.isoformat(),
            tuple(round(float(getattr(payload, metric)), 3) for metric in METRIC_FIELDS),
        )
        previous_signature = self._last_signatures.get(payload.locomotive_id)
        if previous_signature == signature:
            self.metrics.duplicate_events_total += 1
            latest = self.get_latest_snapshot(payload.locomotive_id)
            if latest is not None:
                return latest

        self._last_signatures[payload.locomotive_id] = signature

        raw_values = {metric: round(float(getattr(payload, metric)), 2) for metric in METRIC_FIELDS}
        smoothed_values = self._smooth(payload.locomotive_id, raw_values)
        health = calculate_health(smoothed_values, self._health_config)

        snapshot = TelemetrySnapshot(
            locomotive_id=payload.locomotive_id,
            captured_at=captured_at,
            distance_km=payload.distance_km,
            scenario_tag=payload.scenario_tag,
            temperature_c=raw_values["temperature_c"],
            pressure_bar=raw_values["pressure_bar"],
            fuel_level_pct=raw_values["fuel_level_pct"],
            speed_kph=raw_values["speed_kph"],
            smoothed_temperature_c=smoothed_values["temperature_c"],
            smoothed_pressure_bar=smoothed_values["pressure_bar"],
            smoothed_fuel_level_pct=smoothed_values["fuel_level_pct"],
            smoothed_speed_kph=smoothed_values["speed_kph"],
            health_score=health.score,
            health_category=health.category,
            alert_penalty=health.alert_penalty,
            formula=health.formula,
            top_factors=health.top_factors,
            alerts=health.alerts,
            recommendations=health.recommendations,
        )

        stored_snapshot = self.repository.insert_snapshot(snapshot, self._health_config_version)
        self._latest_snapshots[payload.locomotive_id] = stored_snapshot

        self.metrics.ingested_total += 1
        if source == "simulator":
            self.metrics.simulator_generated_total += 1
        else:
            self.metrics.external_ingested_total += 1
        self.metrics.active_alerts_observed_total += len(health.alerts)
        self.metrics.last_ingested_at = captured_at.isoformat()

        self._samples_since_prune += 1
        if self._samples_since_prune >= 50:
            self.repository.prune_older_than(int(self._health_config["retention_hours"]))
            self._samples_since_prune = 0

        self.broker.publish(stored_snapshot.model_dump(mode="json"))
        return stored_snapshot

    def get_latest_snapshot(self, locomotive_id: str) -> TelemetrySnapshot | None:
        cached = self._latest_snapshots.get(locomotive_id)
        if cached is not None:
            return cached
        latest = self.repository.get_latest_snapshot(locomotive_id)
        if latest is not None:
            self._latest_snapshots[locomotive_id] = latest
        return latest

    def get_history(self, locomotive_id: str, minutes: int, limit: int) -> list[TelemetrySnapshot]:
        since = utc_now() - timedelta(minutes=minutes)
        return self.repository.get_snapshots_since(locomotive_id, since, limit)

    def get_replay(self, locomotive_id: str, minutes: int, stride: int, limit: int) -> list[TelemetrySnapshot]:
        items = self.get_history(locomotive_id, minutes=minutes, limit=limit)
        return items[::stride]

    def get_health_history(self, locomotive_id: str, minutes: int, limit: int) -> list[dict[str, Any]]:
        return [
            {
                "captured_at": item.captured_at,
                "health_score": item.health_score,
                "health_category": item.health_category,
            }
            for item in self.get_history(locomotive_id, minutes=minutes, limit=limit)
        ]

    def get_active_alerts(self, locomotive_id: str) -> list[dict[str, Any]]:
        latest = self.get_latest_snapshot(locomotive_id)
        return [item.model_dump(mode="json") for item in latest.alerts] if latest is not None else []

    def get_alert_history(self, locomotive_id: str, minutes: int, limit: int) -> list[AlertSnapshot]:
        snapshots = self.get_history(locomotive_id, minutes=minutes, limit=limit)
        return [
            AlertSnapshot(
                sequence_id=item.sequence_id or 0,
                captured_at=item.captured_at,
                health_score=item.health_score,
                health_category=item.health_category,
                alerts=item.alerts,
            )
            for item in snapshots
            if item.alerts
        ]

    def export_csv(self, locomotive_id: str, minutes: int, limit: int) -> str:
        items = self.get_history(locomotive_id, minutes=minutes, limit=limit)
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "sequence_id",
                "captured_at",
                "locomotive_id",
                "scenario_tag",
                "distance_km",
                "temperature_c",
                "pressure_bar",
                "fuel_level_pct",
                "speed_kph",
                "smoothed_temperature_c",
                "smoothed_pressure_bar",
                "smoothed_fuel_level_pct",
                "smoothed_speed_kph",
                "health_score",
                "health_category",
                "alerts",
                "recommendations",
            ]
        )
        for item in items:
            writer.writerow(
                [
                    item.sequence_id,
                    item.captured_at.isoformat(),
                    item.locomotive_id,
                    item.scenario_tag or "",
                    item.distance_km if item.distance_km is not None else "",
                    item.temperature_c,
                    item.pressure_bar,
                    item.fuel_level_pct,
                    item.speed_kph,
                    item.smoothed_temperature_c,
                    item.smoothed_pressure_bar,
                    item.smoothed_fuel_level_pct,
                    item.smoothed_speed_kph,
                    item.health_score,
                    item.health_category,
                    "; ".join(alert.message for alert in item.alerts),
                    "; ".join(rec.message for rec in item.recommendations),
                ]
            )
        return buffer.getvalue()

    def get_formula_details(self) -> dict[str, Any]:
        return self._formula_details

    def update_config(self, new_config: dict[str, Any], created_by: str | None = None) -> dict[str, Any]:
        config_payload = {
            key: value
            for key, value in new_config.items()
            if key not in {"health_model_version", "created_at", "created_by", "is_active"}
        }
        validate_health_config(config_payload)
        self._health_config_version, self._health_config = self.repository.set_active_health_config(
            config_payload,
            created_by=created_by,
        )
        self._formula_details = self._compose_formula_details()
        return self._formula_details

    def get_service_metrics(self) -> dict[str, Any]:
        return {
            "ingested_total": self.metrics.ingested_total,
            "simulator_generated_total": self.metrics.simulator_generated_total,
            "external_ingested_total": self.metrics.external_ingested_total,
            "duplicate_events_total": self.metrics.duplicate_events_total,
            "active_alerts_observed_total": self.metrics.active_alerts_observed_total,
            "subscriber_count": self.broker.subscriber_count,
            "last_ingested_at": self.metrics.last_ingested_at,
        }

    def metrics_as_prometheus(self) -> str:
        metrics = self.get_service_metrics()
        lines = [
            "# HELP digital_twin_ingested_total Total ingested telemetry events.",
            "# TYPE digital_twin_ingested_total counter",
            f"digital_twin_ingested_total {metrics['ingested_total']}",
            "# HELP digital_twin_simulator_generated_total Total simulator generated events.",
            "# TYPE digital_twin_simulator_generated_total counter",
            f"digital_twin_simulator_generated_total {metrics['simulator_generated_total']}",
            "# HELP digital_twin_duplicate_events_total Duplicate events ignored by the backend.",
            "# TYPE digital_twin_duplicate_events_total counter",
            f"digital_twin_duplicate_events_total {metrics['duplicate_events_total']}",
            "# HELP digital_twin_subscriber_count Current SSE subscribers.",
            "# TYPE digital_twin_subscriber_count gauge",
            f"digital_twin_subscriber_count {metrics['subscriber_count']}",
        ]
        return "\n".join(lines) + "\n"

    def health_status(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "database": str(self.settings.db_path),
            "config_path": str(self.settings.config_path),
            "health_model_version": self._health_config_version,
            "metrics": self.get_service_metrics(),
        }

    def _smooth(self, locomotive_id: str, raw_values: dict[str, float]) -> dict[str, float]:
        previous = self._smoothed_values.get(locomotive_id)
        alpha = float(self._health_config["smoothing"]["alpha"])

        if previous is None:
            smoothed = raw_values.copy()
        else:
            smoothed = {
                metric: round(alpha * raw_values[metric] + (1 - alpha) * previous[metric], 2)
                for metric in METRIC_FIELDS
            }

        self._smoothed_values[locomotive_id] = smoothed
        return smoothed

    def _compose_formula_details(self) -> dict[str, Any]:
        details = describe_formula(self._health_config)
        details["health_model_version"] = self._health_config_version
        return details
