import { startTransition, useEffect, useState } from "react";

import { useAuth } from "@/contexts/AuthContext";
import {
  ApiError,
  buildStreamUrl,
  downloadCsv,
  downloadPdf,
  getHealthModel,
  getHistory,
  getOverview,
  getReplay,
  startSimulator,
  stopSimulator,
  type HealthModelConfig,
  type OverviewResponse,
  type ReplayResponse,
  type SimulatorControlRequest,
  type SimulatorStatus,
  type TelemetrySnapshot,
} from "@/lib/api";

const LIVE_HISTORY_MINUTES = 30;
const LIVE_HISTORY_LIMIT = 180;
const DEFAULT_REPLAY_MINUTES = 15;
const DEFAULT_REPLAY_STRIDE = 2;
const DEFAULT_REPLAY_LIMIT = 240;

export interface TelemetryState {
  loading: boolean;
  error: string | null;
  connected: boolean;
  latest: TelemetrySnapshot | null;
  history: TelemetrySnapshot[];
  replay: ReplayResponse | null;
  formula: HealthModelConfig | null;
  serviceMetrics: OverviewResponse["service_metrics"];
  simulator: SimulatorStatus | null;
  refreshAll: () => Promise<void>;
  refreshReplay: (minutes?: number, stride?: number) => Promise<void>;
  runSimulator: (request: SimulatorControlRequest) => Promise<void>;
  haltSimulator: () => Promise<void>;
  exportHistoryCsv: (minutes?: number) => Promise<void>;
  exportHistoryPdf: (minutes?: number) => Promise<void>;
}

export function useTelemetry(locomotiveId: string): TelemetryState {
  const { token, logout } = useAuth();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [latest, setLatest] = useState<TelemetrySnapshot | null>(null);
  const [history, setHistory] = useState<TelemetrySnapshot[]>([]);
  const [replay, setReplay] = useState<ReplayResponse | null>(null);
  const [formula, setFormula] = useState<HealthModelConfig | null>(null);
  const [serviceMetrics, setServiceMetrics] = useState<OverviewResponse["service_metrics"]>({});
  const [simulator, setSimulator] = useState<SimulatorStatus | null>(null);

  async function withAuthGuard<T>(action: () => Promise<T>): Promise<T> {
    try {
      return await action();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
      }
      throw err;
    }
  }

  async function loadReplay(minutes = DEFAULT_REPLAY_MINUTES, stride = DEFAULT_REPLAY_STRIDE) {
    if (!token) {
      return;
    }
    const replayResponse = await withAuthGuard(() =>
      getReplay(token, locomotiveId, minutes, stride, DEFAULT_REPLAY_LIMIT),
    );
    setReplay(replayResponse);
  }

  async function loadOverviewBundle(showLoader = false) {
    if (!token) {
      return;
    }

    if (showLoader) {
      setLoading(true);
    }
    setError(null);

    try {
      const [overview, historyResponse, formulaResponse] = await withAuthGuard(() =>
        Promise.all([
          getOverview(token, locomotiveId),
          getHistory(token, locomotiveId, LIVE_HISTORY_MINUTES, LIVE_HISTORY_LIMIT),
          getHealthModel(token),
        ]),
      );

      setLatest(overview.latest);
      setServiceMetrics(overview.service_metrics || {});
      setSimulator(overview.simulator);
      setHistory(historyResponse.items);
      setFormula(formulaResponse);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load telemetry";
      setError(message);
    } finally {
      if (showLoader) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setLatest(null);
      setHistory([]);
      setReplay(null);
      setFormula(null);
      setSimulator(null);
      setServiceMetrics({});
      setConnected(false);
      return;
    }

    setReplay(null);
    loadOverviewBundle(true);
    loadReplay();
    // `token` and `locomotiveId` changes should force a new load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, locomotiveId]);

  useEffect(() => {
    if (!token) {
      return;
    }

    const interval = window.setInterval(() => {
      loadOverviewBundle(false);
    }, 12000);

    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, locomotiveId]);

  useEffect(() => {
    if (!token) {
      return;
    }

    const stream = new EventSource(buildStreamUrl(token, locomotiveId));

    stream.onopen = () => {
      setConnected(true);
      setError(null);
    };

    stream.onerror = () => {
      setConnected(false);
    };

    const handleSnapshot = (event: MessageEvent) => {
      try {
        const snapshot = JSON.parse(event.data) as TelemetrySnapshot;
        if (snapshot.locomotive_id !== locomotiveId) {
          return;
        }

        startTransition(() => {
          setLatest(snapshot);
          setHistory(previous => {
            const next = [...previous, snapshot];
            return next.slice(-LIVE_HISTORY_LIMIT);
          });
        });
      } catch {
        setError("Received malformed telemetry event");
      }
    };

    stream.addEventListener("snapshot", handleSnapshot as EventListener);

    return () => {
      setConnected(false);
      stream.removeEventListener("snapshot", handleSnapshot as EventListener);
      stream.close();
    };
  }, [token, locomotiveId]);

  return {
    loading,
    error,
    connected,
    latest,
    history,
    replay,
    formula,
    serviceMetrics,
    simulator,
    refreshAll: async () => {
      await loadOverviewBundle(true);
    },
    refreshReplay: async (minutes = DEFAULT_REPLAY_MINUTES, stride = DEFAULT_REPLAY_STRIDE) => {
      try {
        setError(null);
        await loadReplay(minutes, stride);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load replay";
        setError(message);
      }
    },
    runSimulator: async (request: SimulatorControlRequest) => {
      if (!token) {
        return;
      }
      try {
        setError(null);
        const status = await withAuthGuard(() => startSimulator(token, request));
        setSimulator(status);
        await loadOverviewBundle(false);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to start simulator";
        setError(message);
      }
    },
    haltSimulator: async () => {
      if (!token) {
        return;
      }
      try {
        setError(null);
        const status = await withAuthGuard(() => stopSimulator(token));
        setSimulator(status);
        await loadOverviewBundle(false);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to stop simulator";
        setError(message);
      }
    },
    exportHistoryCsv: async (minutes = LIVE_HISTORY_MINUTES) => {
      if (!token) {
        return;
      }
      try {
        await withAuthGuard(() => downloadCsv(token, locomotiveId, minutes));
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to export CSV";
        setError(message);
      }
    },
    exportHistoryPdf: async (minutes = LIVE_HISTORY_MINUTES) => {
      if (!token) {
        return;
      }
      try {
        await withAuthGuard(() => downloadPdf(token, locomotiveId, minutes));
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to export PDF";
        setError(message);
      }
    },
  };
}
