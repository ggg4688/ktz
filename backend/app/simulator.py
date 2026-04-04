from __future__ import annotations

import asyncio
import logging
import math
import random
from datetime import timedelta

from app.engine import TelemetryEngine
from app.models import SimulatorControlRequest, SimulatorStatus, TelemetryIn
from app.repository import utc_now

logger = logging.getLogger(__name__)


class TelemetrySimulator:
    def __init__(self, engine: TelemetryEngine, default_locomotive_id: str) -> None:
        self.engine = engine
        self._rng = random.Random(42)
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._scenario = "baseline"
        self._interval_ms = 1000
        self._burst_size = 1
        self._load_multiplier = 1.0
        self._locomotive_id = default_locomotive_id
        self._tick = 0
        self._distance_km = 0.0
        self._fuel_level_pct = 86.0
        self._last_emitted_at = None

    async def start(self, control: SimulatorControlRequest | None = None) -> SimulatorStatus:
        if control is None:
            control = SimulatorControlRequest(locomotive_id=self._locomotive_id)

        await self.stop()

        self._scenario = control.scenario
        self._interval_ms = control.interval_ms
        self._burst_size = control.burst_size
        self._load_multiplier = control.load_multiplier
        self._locomotive_id = control.locomotive_id

        if control.reset_state:
            self._reset_state()

        self._running = True
        self._task = asyncio.create_task(self._run(), name="telemetry-simulator")
        return self.status()

    async def stop(self) -> SimulatorStatus:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        return self.status()

    def status(self) -> SimulatorStatus:
        return SimulatorStatus(
            running=self._running,
            scenario=self._scenario,
            interval_ms=self._interval_ms,
            burst_size=self._burst_size,
            load_multiplier=self._load_multiplier,
            locomotive_id=self._locomotive_id,
            tick=self._tick,
            distance_km=round(self._distance_km, 3),
            fuel_level_pct=round(self._fuel_level_pct, 2),
            last_emitted_at=self._last_emitted_at,
        )

    async def _run(self) -> None:
        try:
            while self._running:
                for index in range(self._burst_size):
                    reading = self._next_reading(index)
                    snapshot = self.engine.ingest(reading, source="simulator")
                    self._last_emitted_at = snapshot.captured_at
                await asyncio.sleep(self._interval_ms / 1000)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telemetry simulator stopped due to an unexpected error")
            self._running = False

    def _reset_state(self) -> None:
        self._tick = 0
        self._distance_km = 0.0
        self._fuel_level_pct = 34.0 if self._scenario == "low_fuel" else 86.0
        self._last_emitted_at = None

    def _next_reading(self, burst_index: int) -> TelemetryIn:
        self._tick += 1

        speed = 82 + self._wave(14, 6.5) + self._noise(3.0)
        temperature = 84 + self._wave(4.5, 9.0) + self._noise(1.2)
        pressure = 6.6 + self._wave(0.35, 8.0) + self._noise(0.12)

        if self._scenario == "overheat":
            if self._tick > 20:
                temperature += min(28, (self._tick - 20) * 0.75)
            speed -= 8
        elif self._scenario == "pressure_drop":
            if self._tick > 18:
                pressure -= min(4.2, (self._tick - 18) * 0.09)
                temperature += min(9, (self._tick - 18) * 0.18)
        elif self._scenario == "low_fuel":
            self._fuel_level_pct -= 0.45 * self._load_multiplier
        elif self._scenario == "mixed_failure":
            if self._tick > 15:
                temperature += min(20, (self._tick - 15) * 0.5)
            if self._tick > 28:
                pressure -= min(3.8, (self._tick - 28) * 0.08)
            if self._tick > 38:
                speed += min(24, (self._tick - 38) * 0.4)
                self._fuel_level_pct -= 0.35 * self._load_multiplier

        self._fuel_level_pct -= (0.08 + max(speed, 0) / 800) * self._load_multiplier
        self._fuel_level_pct = self._clamp(self._fuel_level_pct, 0, 100)

        event_seconds = self._interval_ms / 1000 / max(self._burst_size, 1)
        self._distance_km += max(speed, 0) * event_seconds / 3600

        captured_at = utc_now() + timedelta(milliseconds=burst_index)

        return TelemetryIn(
            locomotive_id=self._locomotive_id,
            captured_at=captured_at,
            temperature_c=round(self._clamp(temperature, 35, 130), 2),
            pressure_bar=round(self._clamp(pressure, 0.2, 12), 2),
            fuel_level_pct=round(self._fuel_level_pct, 2),
            speed_kph=round(self._clamp(speed, 0, 150), 2),
            distance_km=round(self._distance_km, 3),
            scenario_tag=self._scenario,
        )

    def _wave(self, amplitude: float, divisor: float) -> float:
        return amplitude * math.sin(self._tick / divisor)

    def _noise(self, span: float) -> float:
        return self._rng.uniform(-span, span)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
