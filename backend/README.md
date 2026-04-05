# Locomotive Digital Twin Backend

Python backend for the locomotive telemetry case. It covers the backend-owned part:

- telemetry ingestion and normalization;
- a built-in simulator for demo mode;
- transparent health index calculation;
- alerts and recommendations;
- recent history, replay window, and CSV/PDF export;
- service health and basic metrics.
- JWT authentication with RBAC.
- OpenAPI docs via Swagger UI and ReDoc.

## Stack

- FastAPI
- SQLite
- standard-library background simulator
- Server-Sent Events for a lightweight live stream
- optional Go websocket broadcaster for realtime fan-out

## Database

SQLite is now the primary project database. On startup the backend creates and migrates:

- `users`
- `locomotives`
- `health_model_configs`
- `telemetry_snapshots`
- `alert_events`

The initial demo users and the initial health-model config are seeded from `app/users.json` and `app/settings.json` only when the database is empty. After that, auth and health-model changes are read from the database.

## Run

From the `backend` directory:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Swagger and OpenAPI:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`
- `http://127.0.0.1:8000/openapi.json`

The simulator starts automatically by default. If you want only external ingestion:

```powershell
$env:DIGITAL_TWIN_AUTO_START_SIMULATOR='false'
python -m uvicorn app.main:app --reload
```

## Realtime WebSocket Service

The websocket broadcaster now lives in `backend/services/realtime_websocket`.

Run it in a separate terminal:

```powershell
cd backend/services/realtime_websocket
go run ./cmd
```

Then point the Python backend at it:

```powershell
$env:DIGITAL_TWIN_REALTIME_WS_URL='ws://127.0.0.1:8080/ws'
python -m uvicorn app.main:app --reload
```

The backend derives the correct `Origin` header automatically. If you need to override it, set `DIGITAL_TWIN_REALTIME_WS_ORIGIN`.

## Auth

Most business endpoints require a bearer token.

Demo users:

- `admin` / `admin123`
- `operator` / `operator123`
- `viewer` / `viewer123`

Roles:

- `viewer`: read dashboards, history, alerts, replay, export, stream
- `operator`: viewer permissions plus telemetry ingest and simulator control
- `admin`: operator permissions plus metrics, health-model updates, and user management

Login example:

```powershell
$token = (Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/auth/login -ContentType 'application/json' -Body '{"username":"admin","password":"admin123"}').access_token
Invoke-RestMethod -Headers @{ Authorization = "Bearer $token" } -Uri http://127.0.0.1:8000/api/v1/auth/me
```

For SSE in a browser client, use the query-string fallback:

```text
/api/v1/stream?access_token=<JWT>
```

## Main endpoints

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/admin/users`
- `POST /api/v1/admin/users`
- `GET /healthz`
- `GET /metrics`
- `GET /api/v1/overview`
- `POST /api/v1/telemetry`
- `POST /api/v1/telemetry/batch`
- `GET /api/v1/telemetry/history`
- `GET /api/v1/replay`
- `GET /api/v1/health-index/current`
- `GET /api/v1/health-index/history`
- `GET /api/v1/alerts/active`
- `GET /api/v1/alerts/history`
- `GET /api/v1/config/health-model`
- `PUT /api/v1/config/health-model`
- `GET /api/v1/export/csv`
- `GET /api/v1/export/pdf`
- `GET /api/v1/stream`
- `GET /api/v1/simulator/status`
- `POST /api/v1/simulator/start`
- `POST /api/v1/simulator/stop`

`GET /api/v1/admin/users`, `POST /api/v1/admin/users`, `GET /metrics`, and `PUT /api/v1/config/health-model` require an `admin` JWT.

`GET /healthz` now also reports `realtime_websocket` bridge status, and `/metrics` includes `digital_twin_realtime_ws_*` counters.

## Health index

The score is config-driven and stored in the database. `app/settings.json` is only the seed source for a brand-new database.

Formula:

```text
health_score = 100
               - sum(metric_penalty * metric_weight * 100)
               - min(alert_penalty_cap, sum(active_alert_severity_penalties))
```

- each metric penalty is normalized into the `0..1` range;
- weights stay transparent in config;
- active alerts add extra penalties;
- category thresholds are also config-driven.

Current metric set:

- `temperature_c`
- `pressure_bar`
- `fuel_level_pct`
- `speed_kph`

## Demo notes

- default simulator scenario is `baseline`;
- use `mixed_failure` or `overheat` for judging demos;
- raise `burst_size` to simulate higher event rates without changing frontend code.

Example:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/simulator/start -ContentType 'application/json' -Body '{"scenario":"mixed_failure","interval_ms":1000,"burst_size":10,"load_multiplier":1.2}'
```
