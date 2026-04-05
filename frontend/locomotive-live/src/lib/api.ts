export type RoleName = "viewer" | "operator" | "admin";

export interface PublicUser {
  username: string;
  full_name: string;
  role: RoleName;
}

export interface CreateUserRequest {
  username: string;
  password: string;
  full_name?: string | null;
  role: RoleName;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: PublicUser;
}

export interface FactorContribution {
  metric: string;
  label: string;
  weight: number;
  penalty: number;
  score_impact: number;
  current_value: number;
}

export interface AlertItem {
  code: string;
  severity: "warning" | "critical";
  metric: string;
  message: string;
  recommendation: string;
}

export interface RecommendationItem {
  code: string;
  priority: number;
  message: string;
}

export interface TelemetrySnapshot {
  sequence_id: number | null;
  locomotive_id: string;
  captured_at: string;
  distance_km: number | null;
  scenario_tag: string | null;
  temperature_c: number;
  pressure_bar: number;
  fuel_level_pct: number;
  speed_kph: number;
  smoothed_temperature_c: number;
  smoothed_pressure_bar: number;
  smoothed_fuel_level_pct: number;
  smoothed_speed_kph: number;
  health_score: number;
  health_category: "normal" | "attention" | "critical";
  alert_penalty: number;
  formula: string;
  top_factors: FactorContribution[];
  alerts: AlertItem[];
  recommendations: RecommendationItem[];
}

export interface TelemetryWindowResponse {
  locomotive_id: string;
  from_at: string;
  to_at: string;
  sample_count: number;
  items: TelemetrySnapshot[];
}

export interface ReplayResponse {
  locomotive_id: string;
  from_at: string;
  to_at: string;
  stride: number;
  frame_count: number;
  frames: TelemetrySnapshot[];
}

export interface SimulatorStatus {
  running: boolean;
  scenario: string;
  interval_ms: number;
  burst_size: number;
  load_multiplier: number;
  locomotive_id: string;
  tick: number;
  distance_km: number;
  fuel_level_pct: number;
  last_emitted_at: string | null;
}

export interface OverviewResponse {
  latest: TelemetrySnapshot | null;
  active_alerts: AlertItem[];
  recommendations: RecommendationItem[];
  service_metrics: Record<string, number | string | null>;
  simulator: SimulatorStatus;
}

export interface HealthMetricConfig {
  label: string;
  weight: number;
  direction: "range" | "low_only" | "high_only";
  ideal_min?: number;
  ideal_max?: number;
  safe_min?: number;
  safe_max?: number;
  warning_low?: number;
  critical_low?: number;
  warning_high?: number;
  critical_high?: number;
}

export interface HealthModelConfig {
  formula: string;
  retention_hours: number;
  smoothing: {
    alpha: number;
  };
  categories: {
    normal_min: number;
    attention_min: number;
  };
  alert_penalty_cap: number;
  severity_penalties: Record<string, number>;
  metrics: Record<string, HealthMetricConfig>;
  health_model_version: number;
}

export interface SimulatorControlRequest {
  scenario: "baseline" | "overheat" | "pressure_drop" | "low_fuel" | "mixed_failure";
  interval_ms: number;
  burst_size: number;
  load_multiplier: number;
  locomotive_id: string;
  reset_state: boolean;
}

export interface StoredSession {
  accessToken: string;
  expiresAt: string;
  user: PublicUser;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export function getApiBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, "");
}

export function getDefaultLocomotiveId(): string {
  return import.meta.env.VITE_DEFAULT_LOCOMOTIVE_ID || "locomotive-01";
}

export function buildApiUrl(
  path: string,
  query?: Record<string, string | number | boolean | undefined | null>,
): string {
  const url = new URL(`${getApiBaseUrl()}${path}`);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") {
        return;
      }
      url.searchParams.set(key, String(value));
    });
  }
  return url.toString();
}

async function requestJson<T>(
  path: string,
  options: RequestInit & {
    token?: string | null;
    query?: Record<string, string | number | boolean | undefined | null>;
  } = {},
): Promise<T> {
  const { token, query, headers, ...requestInit } = options;

  const response = await fetch(buildApiUrl(path, query), {
    ...requestInit,
    headers: {
      ...(headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(
        requestInit.body && !(requestInit.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}
      ),
    },
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail || payload.message || message;
    } catch {
      try {
        const text = await response.text();
        if (text) {
          message = text;
        }
      } catch {
        // Ignore secondary parse failures.
      }
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function loginRequest(username: string, password: string): Promise<TokenResponse> {
  return requestJson<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function getCurrentUser(token: string): Promise<PublicUser> {
  return requestJson<PublicUser>("/api/v1/auth/me", { token });
}

export async function listUsers(token: string): Promise<PublicUser[]> {
  return requestJson<PublicUser[]>("/api/v1/admin/users", { token });
}

export async function createUser(token: string, payload: CreateUserRequest): Promise<PublicUser> {
  return requestJson<PublicUser>("/api/v1/admin/users", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export async function getOverview(token: string, locomotiveId: string): Promise<OverviewResponse> {
  return requestJson<OverviewResponse>("/api/v1/overview", {
    token,
    query: { locomotive_id: locomotiveId },
  });
}

export async function getHistory(
  token: string,
  locomotiveId: string,
  minutes: number,
  limit: number,
): Promise<TelemetryWindowResponse> {
  return requestJson<TelemetryWindowResponse>("/api/v1/telemetry/history", {
    token,
    query: {
      locomotive_id: locomotiveId,
      minutes,
      limit,
    },
  });
}

export async function getReplay(
  token: string,
  locomotiveId: string,
  minutes: number,
  stride: number,
  limit: number,
): Promise<ReplayResponse> {
  return requestJson<ReplayResponse>("/api/v1/replay", {
    token,
    query: {
      locomotive_id: locomotiveId,
      minutes,
      stride,
      limit,
    },
  });
}

export async function getHealthModel(token: string): Promise<HealthModelConfig> {
  return requestJson<HealthModelConfig>("/api/v1/config/health-model", { token });
}

export async function updateHealthModel(token: string, config: HealthModelConfig): Promise<HealthModelConfig> {
  return requestJson<HealthModelConfig>("/api/v1/config/health-model", {
    method: "PUT",
    token,
    body: JSON.stringify(config),
  });
}

export async function getSimulatorStatus(token: string): Promise<SimulatorStatus> {
  return requestJson<SimulatorStatus>("/api/v1/simulator/status", { token });
}

export async function startSimulator(
  token: string,
  request: SimulatorControlRequest,
): Promise<SimulatorStatus> {
  return requestJson<SimulatorStatus>("/api/v1/simulator/start", {
    method: "POST",
    token,
    body: JSON.stringify(request),
  });
}

export async function stopSimulator(token: string): Promise<SimulatorStatus> {
  return requestJson<SimulatorStatus>("/api/v1/simulator/stop", {
    method: "POST",
    token,
  });
}

export async function downloadCsv(
  token: string,
  locomotiveId: string,
  minutes: number,
  limit = 3000,
): Promise<void> {
  const response = await fetch(
    buildApiUrl("/api/v1/export/csv", {
      locomotive_id: locomotiveId,
      minutes,
      limit,
    }),
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  if (!response.ok) {
    throw new ApiError(`CSV export failed with status ${response.status}`, response.status);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = `${locomotiveId}-telemetry.csv`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export async function downloadPdf(
  token: string,
  locomotiveId: string,
  minutes: number,
  limit = 3000,
): Promise<void> {
  const response = await fetch(
    buildApiUrl("/api/v1/export/pdf", {
      locomotive_id: locomotiveId,
      minutes,
      limit,
    }),
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  if (!response.ok) {
    throw new ApiError(`PDF export failed with status ${response.status}`, response.status);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = `${locomotiveId}-report.pdf`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export function buildStreamUrl(token: string, locomotiveId: string): string {
  return buildApiUrl("/api/v1/stream", {
    access_token: token,
    locomotive_id: locomotiveId,
  });
}
