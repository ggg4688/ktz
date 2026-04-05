import { useState } from "react";
import {
  Activity,
  ArrowDownUp,
  Fuel,
  Gauge,
  RefreshCw,
  Route,
  Thermometer,
  Wifi,
  WifiOff,
} from "lucide-react";

import AlertsPanel from "@/components/AlertsPanel";
import FormulaPanel from "@/components/FormulaPanel";
import HealthIndex from "@/components/HealthIndex";
import MetricCard from "@/components/MetricCard";
import RecommendationsPanel from "@/components/RecommendationsPanel";
import ReplayPanel from "@/components/ReplayPanel";
import SimulatorPanel from "@/components/SimulatorPanel";
import TelemetryChart from "@/components/TelemetryChart";
import RouteSectionMap from "@/components/RouteSectionMap";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import { getDefaultLocomotiveId } from "@/lib/api";
import { useTelemetry } from "@/hooks/useTelemetry";

function formatMetricValue(value: number | string | null | undefined): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  return String(value);
}

export default function Dashboard() {
  const { canOperate, user } = useAuth();
  const [locomotiveId, setLocomotiveId] = useState(getDefaultLocomotiveId());
  const telemetry = useTelemetry(locomotiveId);

  const latest = telemetry.latest;

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-3xl border border-border/70 bg-[linear-gradient(135deg,hsl(var(--card)),hsl(222_44%_8%))] p-6 shadow-xl shadow-black/10">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="secondary">Live digital twin</Badge>
              <Badge variant="outline">{user?.role}</Badge>
              {telemetry.connected ? (
                <Badge variant="default" className="gap-2">
                  <Wifi className="h-3.5 w-3.5" />
                  SSE connected
                </Badge>
              ) : (
                <Badge variant="secondary" className="gap-2">
                  <WifiOff className="h-3.5 w-3.5" />
                  reconnecting
                </Badge>
              )}
            </div>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">Locomotive telemetry control room</h1>
              <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
                Monitor live metrics, explain the health index, review replay frames, and drive demo scenarios
                from the same dashboard.
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-[minmax(0,220px)_auto_auto_auto]">
            <Input
              value={locomotiveId}
              onChange={(event) => setLocomotiveId(event.target.value)}
              className="bg-secondary/60"
              placeholder="Locomotive ID"
            />
            <Button variant="secondary" onClick={() => telemetry.refreshAll()} disabled={telemetry.loading}>
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            <Button variant="outline" onClick={() => telemetry.exportHistoryCsv()} disabled={!latest}>
              Export CSV
            </Button>
            <Button variant="outline" onClick={() => telemetry.exportHistoryPdf()} disabled={!latest}>
              Export PDF
            </Button>
          </div>
        </div>

        {telemetry.error ? (
          <p className="mt-4 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {telemetry.error}
          </p>
        ) : null}
      </section>

      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <HealthIndex
          value={latest?.health_score || 0}
          category={latest?.health_category}
          capturedAt={latest?.captured_at}
        />

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard
            label="Speed"
            value={latest?.speed_kph || 0}
            unit="km/h"
            icon={Gauge}
            colorClass="text-chart-speed"
            secondaryValue={latest ? `Smoothed ${latest.smoothed_speed_kph.toFixed(1)} km/h` : undefined}
          />
          <MetricCard
            label="Temperature"
            value={latest?.temperature_c || 0}
            unit="°C"
            icon={Thermometer}
            colorClass="text-chart-temp"
            secondaryValue={latest ? `Smoothed ${latest.smoothed_temperature_c.toFixed(1)} °C` : undefined}
          />
          <MetricCard
            label="Pressure"
            value={latest?.pressure_bar || 0}
            unit="bar"
            icon={ArrowDownUp}
            colorClass="text-chart-pressure"
            secondaryValue={latest ? `Smoothed ${latest.smoothed_pressure_bar.toFixed(2)} bar` : undefined}
          />
          <MetricCard
            label="Fuel"
            value={latest?.fuel_level_pct || 0}
            unit="%"
            icon={Fuel}
            colorClass="text-chart-fuel"
            secondaryValue={latest?.scenario_tag ? `Scenario ${latest.scenario_tag}` : "Live reserve"}
          />
          <MetricCard
            label="Distance"
            value={latest?.distance_km || 0}
            unit="km"
            icon={Route}
            colorClass="text-primary"
            secondaryValue={latest ? `Sequence ${latest.sequence_id}` : undefined}
          />
        </div>
      </div>

      <div className="grid gap-6 2xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.8fr)]">
        <TelemetryChart history={telemetry.history} />
        <div className="grid gap-6">
          <AlertsPanel alerts={latest?.alerts || []} capturedAt={latest?.captured_at || null} />
          <RecommendationsPanel recommendations={latest?.recommendations || []} />
        </div>
      </div>

      <RouteSectionMap distanceKm={latest?.distance_km} speedKph={latest?.speed_kph} />

      <div className="grid gap-6 2xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <ReplayPanel replay={telemetry.replay} onRefresh={telemetry.refreshReplay} />
        <FormulaPanel formula={telemetry.formula} topFactors={latest?.top_factors || []} />
      </div>

      <div className="grid gap-6 2xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <SimulatorPanel
          simulator={telemetry.simulator}
          locomotiveId={locomotiveId}
          canOperate={canOperate}
          onStart={telemetry.runSimulator}
          onStop={telemetry.haltSimulator}
        />

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Service and demo status</CardTitle>
            <CardDescription>
              Current flow counters and simulator snapshot that can be shown during the pitch.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              {Object.entries(telemetry.serviceMetrics).map(([key, value]) => (
                <div key={key} className="rounded-xl border border-border/80 bg-secondary/25 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    {key.replaceAll("_", " ")}
                  </p>
                  <p className="mt-2 text-lg font-semibold">{formatMetricValue(value)}</p>
                </div>
              ))}
            </div>

            <div className="rounded-xl border border-border/80 p-4">
              <div className="mb-3 flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" />
                <p className="font-medium">Simulator snapshot</p>
              </div>
              {telemetry.simulator ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <p className="text-sm text-muted-foreground">
                    Scenario: <span className="text-foreground">{telemetry.simulator.scenario}</span>
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Burst: <span className="text-foreground">{telemetry.simulator.burst_size}</span>
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Interval: <span className="text-foreground">{telemetry.simulator.interval_ms} ms</span>
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Load: <span className="text-foreground">{telemetry.simulator.load_multiplier}</span>
                  </p>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Simulator status is not available.</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
