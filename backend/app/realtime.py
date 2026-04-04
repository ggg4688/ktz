from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from websockets.asyncio.client import connect

from app.config import AppSettings

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_origin_from_ws_url(url: str | None) -> str | None:
    if not url:
        return None

    parsed = urlsplit(url)
    if parsed.scheme not in {"ws", "wss"} or not parsed.netloc:
        return None

    scheme = "https" if parsed.scheme == "wss" else "http"
    return f"{scheme}://{parsed.netloc}"


@dataclass(slots=True)
class RealtimeBridgeMetrics:
    published_total: int = 0
    dropped_total: int = 0
    last_published_at: str | None = None
    last_error: str | None = None


class RealtimeWebSocketBridge:
    def __init__(self, settings: AppSettings) -> None:
        self._url = settings.realtime_websocket_url
        self._origin = settings.realtime_websocket_origin or build_origin_from_ws_url(self._url)
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=max(1, settings.realtime_websocket_queue_size))
        self._reconnect_seconds = max(1, settings.realtime_websocket_reconnect_seconds)
        self._metrics = RealtimeBridgeMetrics()
        self._task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event = asyncio.Event()
        self._connected = False

    @property
    def enabled(self) -> bool:
        return bool(self._url)

    async def start(self) -> None:
        if not self.enabled or self._task is not None:
            return

        self._loop = asyncio.get_running_loop()
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="realtime-websocket-bridge")

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return

        self._stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            self._connected = False

    def publish(self, payload: dict[str, Any]) -> None:
        if not self.enabled or self._loop is None:
            return

        encoded = json.dumps(payload, default=str)
        self._loop.call_soon_threadsafe(self._enqueue, encoded)

    def get_metrics(self) -> dict[str, int | str | None]:
        return {
            "realtime_ws_enabled": int(self.enabled),
            "realtime_ws_connected": int(self._connected),
            "realtime_ws_published_total": self._metrics.published_total,
            "realtime_ws_dropped_total": self._metrics.dropped_total,
            "realtime_ws_last_published_at": self._metrics.last_published_at,
        }

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "url": self._url,
            "origin": self._origin,
            "connected": self._connected,
            "queued_messages": self._queue.qsize(),
            "published_total": self._metrics.published_total,
            "dropped_total": self._metrics.dropped_total,
            "last_published_at": self._metrics.last_published_at,
            "last_error": self._metrics.last_error,
        }

    def _enqueue(self, payload: str) -> None:
        if self._queue.full():
            try:
                self._queue.get_nowait()
                self._metrics.dropped_total += 1
            except asyncio.QueueEmpty:
                pass

        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            self._metrics.dropped_total += 1

    async def _run(self) -> None:
        assert self._url is not None

        while not self._stop_event.is_set():
            try:
                async with connect(
                    self._url,
                    origin=self._origin,
                    open_timeout=5,
                    ping_interval=20,
                    ping_timeout=20,
                    max_queue=16,
                ) as websocket:
                    self._connected = True
                    self._metrics.last_error = None
                    logger.info("Connected to realtime websocket bridge at %s", self._url)
                    receiver_task = asyncio.create_task(self._discard_incoming(websocket))

                    try:
                        while not self._stop_event.is_set():
                            try:
                                payload = await asyncio.wait_for(self._queue.get(), timeout=1)
                            except asyncio.TimeoutError:
                                continue
                            await websocket.send(payload)
                            self._metrics.published_total += 1
                            self._metrics.last_published_at = utc_now().isoformat()
                    finally:
                        receiver_task.cancel()
                        try:
                            await receiver_task
                        except asyncio.CancelledError:
                            pass
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._metrics.last_error = str(exc)
                logger.warning("Realtime websocket bridge disconnected from %s: %s", self._url, exc)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._reconnect_seconds)
                except asyncio.TimeoutError:
                    continue
            finally:
                self._connected = False

    async def _discard_incoming(self, websocket: Any) -> None:
        try:
            async for _ in websocket:
                continue
        except asyncio.CancelledError:
            raise
        except Exception:
            return
