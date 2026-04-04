from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import AuthService
from app.config import AppSettings, get_settings
from app.engine import EventBroker, TelemetryEngine
from app.models import (
    AlertHistoryResponse,
    BatchIngestResponse,
    CreateUserRequest,
    LoginRequest,
    OverviewResponse,
    PublicUser,
    ReplayResponse,
    RoleName,
    SimulatorControlRequest,
    SimulatorStatus,
    TelemetryIn,
    TelemetrySnapshot,
    TelemetryWindowResponse,
    TokenResponse,
)
from app.realtime import RealtimeWebSocketBridge
from app.repository import SnapshotRepository, utc_now
from app.simulator import TelemetrySimulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

bearer_scheme = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    repository = SnapshotRepository(settings)
    broker = EventBroker()
    realtime_bridge = RealtimeWebSocketBridge(settings)
    await realtime_bridge.start()
    engine = TelemetryEngine(settings, repository, broker, realtime_bridge)
    simulator = TelemetrySimulator(engine, settings.default_locomotive_id)
    auth_service = AuthService(settings, repository)

    app.state.settings = settings
    app.state.repository = repository
    app.state.broker = broker
    app.state.realtime_bridge = realtime_bridge
    app.state.engine = engine
    app.state.simulator = simulator
    app.state.auth_service = auth_service

    if settings.auto_start_simulator:
        await simulator.start(
            SimulatorControlRequest(
                locomotive_id=settings.default_locomotive_id,
            )
        )

    try:
        yield
    finally:
        await simulator.stop()
        await realtime_bridge.stop()
        repository.close()


app = FastAPI(
    title="Locomotive Digital Twin Backend",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"persistAuthorization": True},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_engine(request: Request) -> TelemetryEngine:
    return request.app.state.engine


def get_simulator(request: Request) -> TelemetrySimulator:
    return request.app.state.simulator


def get_broker(request: Request) -> EventBroker:
    return request.app.state.broker


def get_runtime_settings(request: Request) -> AppSettings:
    return request.app.state.settings


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> PublicUser:
    token: str | None = None

    if credentials is not None:
        if credentials.scheme.lower() != "bearer":
            raise _unauthorized("Unsupported authorization scheme")
        token = credentials.credentials
    elif request.query_params.get("access_token"):
        token = request.query_params.get("access_token")

    if not token:
        raise _unauthorized("Missing bearer token")

    try:
        return auth_service.get_user_from_token(token)
    except ValueError as exc:
        raise _unauthorized(str(exc)) from exc


def require_min_role(required_role: RoleName):
    def dependency(current_user: PublicUser = Depends(get_current_user)) -> PublicUser:
        if not AuthService.role_allows(current_user.role, required_role):
            raise HTTPException(status_code=403, detail=f"{required_role} role required")
        return current_user

    return dependency


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "locomotive-digital-twin-backend",
        "timestamp": utc_now().isoformat(),
        "docs": "/docs",
    }


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    user = auth_service.authenticate_user(payload.username, payload.password)
    if user is None:
        raise _unauthorized("Invalid username or password")
    return auth_service.issue_token(user)


@app.get("/api/v1/auth/me", response_model=PublicUser)
def me(current_user: PublicUser = Depends(get_current_user)) -> PublicUser:
    return current_user


@app.get("/api/v1/admin/users", response_model=list[PublicUser])
def admin_users(
    auth_service: AuthService = Depends(get_auth_service),
    _: PublicUser = Depends(require_min_role("admin")),
) -> list[PublicUser]:
    return auth_service.list_users()


@app.post("/api/v1/admin/users", response_model=PublicUser, status_code=201)
def admin_create_user(
    payload: CreateUserRequest,
    auth_service: AuthService = Depends(get_auth_service),
    _: PublicUser = Depends(require_min_role("admin")),
) -> PublicUser:
    try:
        return auth_service.create_user(
            username=payload.username,
            password=payload.password,
            role=payload.role,
            full_name=payload.full_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/healthz")
def healthz(engine: TelemetryEngine = Depends(get_engine)) -> dict[str, Any]:
    return engine.health_status()


@app.get("/metrics", response_class=PlainTextResponse)
def metrics(
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("admin")),
) -> str:
    return engine.metrics_as_prometheus()


@app.post("/api/v1/telemetry", response_model=TelemetrySnapshot)
def ingest_telemetry(
    payload: TelemetryIn,
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("operator")),
) -> TelemetrySnapshot:
    return engine.ingest(payload, source="external")


@app.post("/api/v1/telemetry/batch", response_model=BatchIngestResponse)
def ingest_telemetry_batch(
    items: list[TelemetryIn],
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("operator")),
) -> BatchIngestResponse:
    snapshots = [engine.ingest(item, source="external") for item in items]
    last_sequence_id = snapshots[-1].sequence_id if snapshots else None
    return BatchIngestResponse(inserted=len(snapshots), last_sequence_id=last_sequence_id)


@app.get("/api/v1/overview", response_model=OverviewResponse)
def overview(
    locomotive_id: str = Query(default="locomotive-01", min_length=1),
    engine: TelemetryEngine = Depends(get_engine),
    simulator: TelemetrySimulator = Depends(get_simulator),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> OverviewResponse:
    latest = engine.get_latest_snapshot(locomotive_id)
    return OverviewResponse(
        latest=latest,
        active_alerts=latest.alerts if latest is not None else [],
        recommendations=latest.recommendations if latest is not None else [],
        service_metrics=engine.get_service_metrics(),
        simulator=simulator.status().model_dump(mode="json"),
    )


@app.get("/api/v1/telemetry/latest", response_model=TelemetrySnapshot)
def latest_telemetry(
    locomotive_id: str = Query(default="locomotive-01", min_length=1),
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> TelemetrySnapshot:
    latest = engine.get_latest_snapshot(locomotive_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="No telemetry available yet")
    return latest


@app.get("/api/v1/telemetry/history", response_model=TelemetryWindowResponse)
def telemetry_history(
    locomotive_id: str = Query(default="locomotive-01", min_length=1),
    minutes: int = Query(default=15, ge=1, le=4_320),
    limit: int = Query(default=1_500, ge=1, le=10_000),
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> TelemetryWindowResponse:
    items = engine.get_history(locomotive_id, minutes=minutes, limit=limit)
    now = utc_now()
    from_at = items[0].captured_at if items else now
    to_at = items[-1].captured_at if items else now
    return TelemetryWindowResponse(
        locomotive_id=locomotive_id,
        from_at=from_at,
        to_at=to_at,
        sample_count=len(items),
        items=items,
    )


@app.get("/api/v1/replay", response_model=ReplayResponse)
def replay(
    locomotive_id: str = Query(default="locomotive-01", min_length=1),
    minutes: int = Query(default=5, ge=1, le=120),
    stride: int = Query(default=1, ge=1, le=60),
    limit: int = Query(default=3_000, ge=1, le=10_000),
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> ReplayResponse:
    frames = engine.get_replay(locomotive_id, minutes=minutes, stride=stride, limit=limit)
    now = utc_now()
    from_at = frames[0].captured_at if frames else now
    to_at = frames[-1].captured_at if frames else now
    return ReplayResponse(
        locomotive_id=locomotive_id,
        from_at=from_at,
        to_at=to_at,
        stride=stride,
        frame_count=len(frames),
        frames=frames,
    )


@app.get("/api/v1/health-index/current")
def current_health_index(
    locomotive_id: str = Query(default="locomotive-01", min_length=1),
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> dict[str, Any]:
    latest = engine.get_latest_snapshot(locomotive_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="No telemetry available yet")
    return {
        "locomotive_id": latest.locomotive_id,
        "captured_at": latest.captured_at,
        "health_score": latest.health_score,
        "health_category": latest.health_category,
        "alert_penalty": latest.alert_penalty,
        "formula": latest.formula,
        "top_factors": [item.model_dump(mode="json") for item in latest.top_factors],
    }


@app.get("/api/v1/health-index/history")
def health_index_history(
    locomotive_id: str = Query(default="locomotive-01", min_length=1),
    minutes: int = Query(default=15, ge=1, le=4_320),
    limit: int = Query(default=1_500, ge=1, le=10_000),
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> dict[str, Any]:
    return {
        "locomotive_id": locomotive_id,
        "items": engine.get_health_history(locomotive_id, minutes=minutes, limit=limit),
    }


@app.get("/api/v1/alerts/active")
def active_alerts(
    locomotive_id: str = Query(default="locomotive-01", min_length=1),
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> dict[str, Any]:
    return {
        "locomotive_id": locomotive_id,
        "items": engine.get_active_alerts(locomotive_id),
    }


@app.get("/api/v1/alerts/history", response_model=AlertHistoryResponse)
def alert_history(
    locomotive_id: str = Query(default="locomotive-01", min_length=1),
    minutes: int = Query(default=60, ge=1, le=4_320),
    limit: int = Query(default=2_000, ge=1, le=10_000),
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> AlertHistoryResponse:
    items = engine.get_alert_history(locomotive_id, minutes=minutes, limit=limit)
    now = utc_now()
    from_at = items[0].captured_at if items else now
    to_at = items[-1].captured_at if items else now
    return AlertHistoryResponse(
        locomotive_id=locomotive_id,
        from_at=from_at,
        to_at=to_at,
        sample_count=len(items),
        items=items,
    )


@app.get("/api/v1/config/health-model")
def health_model(
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> dict[str, Any]:
    return engine.get_formula_details()


@app.put("/api/v1/config/health-model")
def update_health_model(
    new_config: dict[str, Any],
    engine: TelemetryEngine = Depends(get_engine),
    current_user: PublicUser = Depends(require_min_role("admin")),
) -> dict[str, Any]:
    return engine.update_config(new_config, created_by=current_user.username)


@app.get("/api/v1/export/csv", response_class=PlainTextResponse)
def export_csv(
    locomotive_id: str = Query(default="locomotive-01", min_length=1),
    minutes: int = Query(default=15, ge=1, le=4_320),
    limit: int = Query(default=3_000, ge=1, le=10_000),
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> PlainTextResponse:
    payload = engine.export_csv(locomotive_id, minutes=minutes, limit=limit)
    headers = {"Content-Disposition": f'attachment; filename="{locomotive_id}-telemetry.csv"'}
    return PlainTextResponse(content=payload, media_type="text/csv", headers=headers)


@app.get("/api/v1/stream")
async def stream(
    request: Request,
    locomotive_id: str = Query(default="locomotive-01", min_length=1),
    broker: EventBroker = Depends(get_broker),
    engine: TelemetryEngine = Depends(get_engine),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> StreamingResponse:
    queue = await broker.subscribe()

    async def event_generator():
        latest = engine.get_latest_snapshot(locomotive_id)
        if latest is not None:
            initial_payload = json.dumps(latest.model_dump(mode="json"))
            yield f"event: snapshot\ndata: {initial_payload}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: snapshot\ndata: {payload}\n\n"
        finally:
            broker.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/v1/simulator/status", response_model=SimulatorStatus)
def simulator_status(
    simulator: TelemetrySimulator = Depends(get_simulator),
    _: PublicUser = Depends(require_min_role("viewer")),
) -> SimulatorStatus:
    return simulator.status()


@app.post("/api/v1/simulator/start", response_model=SimulatorStatus)
async def simulator_start(
    control: SimulatorControlRequest,
    simulator: TelemetrySimulator = Depends(get_simulator),
    _: PublicUser = Depends(require_min_role("operator")),
) -> SimulatorStatus:
    return await simulator.start(control)


@app.post("/api/v1/simulator/stop", response_model=SimulatorStatus)
async def simulator_stop(
    simulator: TelemetrySimulator = Depends(get_simulator),
    _: PublicUser = Depends(require_min_role("operator")),
) -> SimulatorStatus:
    return await simulator.stop()
