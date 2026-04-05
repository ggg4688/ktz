# Locomotive Live Frontend

React frontend for the locomotive digital twin demo. It is wired to the Python backend and covers:

- JWT login against the backend
- live telemetry over SSE
- health index visualization
- active alerts and recommendations
- recent history charts with zoom controls
- route section map with current position and speed limits
- replay of historical frames with event markers
- CSV and PDF report export
- simulator controls for operator and admin roles
- health-model inspection and editing for admin
- backend user creation and user list management for admin

## Run

From `frontend/locomotive-live`:

```powershell
npm install
npm run dev
```

Optional environment file:

```powershell
copy .env.example .env
```

Environment variables:

- `VITE_API_BASE_URL`: backend URL, default `http://127.0.0.1:8000`
- `VITE_DEFAULT_LOCOMOTIVE_ID`: default locomotive id, default `locomotive-01`

## Demo accounts

- `admin / admin123`
- `operator / operator123`
- `viewer / viewer123`

## Demo flow

1. Start the backend.
2. Start the frontend with `npm run dev`.
3. Sign in with one of the demo accounts.
4. Use the dashboard for live charts, health logic, alerts, recommendations, and replay.
5. Use simulator controls with `operator` or `admin`.
6. Use the admin page with `admin` to create users, inspect backend accounts, and update the health-model JSON.
