from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

from websockets.asyncio.server import serve

from app.config import AppSettings
from app.realtime import RealtimeWebSocketBridge, build_origin_from_ws_url


class RealtimeBridgeTests(unittest.IsolatedAsyncioTestCase):
    def _settings(self, realtime_url: str | None) -> AppSettings:
        return AppSettings(
            base_dir=Path("."),
            data_dir=Path("."),
            db_path=Path("telemetry.db"),
            config_path=Path("app/settings.json"),
            users_path=Path("app/users.json"),
            jwt_secret="test-secret",
            jwt_issuer="test-issuer",
            jwt_access_token_ttl_minutes=60,
            auto_start_simulator=False,
            default_locomotive_id="locomotive-01",
            cors_origins=["*"],
            realtime_websocket_url=realtime_url,
            realtime_websocket_origin=None,
            realtime_websocket_reconnect_seconds=1,
            realtime_websocket_queue_size=8,
        )

    def test_build_origin_from_ws_url(self) -> None:
        self.assertEqual(build_origin_from_ws_url("ws://127.0.0.1:8080/ws"), "http://127.0.0.1:8080")
        self.assertEqual(build_origin_from_ws_url("wss://example.com/ws"), "https://example.com")
        self.assertIsNone(build_origin_from_ws_url("http://example.com/ws"))

    async def test_bridge_publishes_to_websocket_service(self) -> None:
        received: asyncio.Queue[str] = asyncio.Queue()

        async def handler(connection) -> None:
            async for message in connection:
                await received.put(message)

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            bridge = RealtimeWebSocketBridge(self._settings(f"ws://127.0.0.1:{port}/ws"))
            await bridge.start()

            try:
                payload = {"event": "snapshot", "payload": {"sequence_id": 7, "temperature_c": 88.4}}
                bridge.publish(payload)

                message = await asyncio.wait_for(received.get(), timeout=3)
                self.assertEqual(json.loads(message), payload)

                await asyncio.sleep(0.05)
                status = bridge.status()
                self.assertTrue(status["connected"])
                self.assertEqual(status["published_total"], 1)
                self.assertEqual(status["dropped_total"], 0)
            finally:
                await bridge.stop()
