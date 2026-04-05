import { useEffect, useMemo, useRef, useState } from "react";
import {
  Brush,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TelemetrySnapshot } from "@/lib/api";

interface Props {
  history: TelemetrySnapshot[];
}

type WindowPreset = 5 | 15 | 30;
type MarkerType = "warning" | "critical" | "category";

interface ChartPoint {
  capturedAtIso: string;
  timestamp: string;
  speed: number;
  temperature: number;
  pressure: number;
  fuel: number;
  health: number;
  markerType: MarkerType | null;
}

type MarkerPoint = ChartPoint & { markerType: MarkerType };

function formatTime(value: string): string {
  return new Date(value).toLocaleTimeString();
}

export default function TelemetryChart({ history }: Props) {
  const [windowMinutes, setWindowMinutes] = useState<WindowPreset>(15);
  const [zoomRange, setZoomRange] = useState<{ startIndex: number; endIndex: number } | null>(null);
  const previousDataLengthRef = useRef(0);

  const data = useMemo<ChartPoint[]>(() => {
    if (!history.length) {
      return [];
    }

    const latestTimestamp = new Date(history[history.length - 1].captured_at).getTime();
    const fromTimestamp = latestTimestamp - windowMinutes * 60_000;

    return history
      .filter((snapshot) => new Date(snapshot.captured_at).getTime() >= fromTimestamp)
      .map((snapshot, index, windowed) => {
        const previous = index > 0 ? windowed[index - 1] : null;
        let markerType: MarkerType | null = null;

        if (previous && previous.health_category !== snapshot.health_category) {
          markerType = "category";
        }

        if (snapshot.alerts.length > 0) {
          const previousCodes = new Set((previous?.alerts || []).map((alert) => alert.code));
          const newAlerts = snapshot.alerts.filter((alert) => !previousCodes.has(alert.code));
          if (newAlerts.length > 0) {
            const hasCritical = newAlerts.some((alert) => alert.severity === "critical");
            markerType = hasCritical ? "critical" : "warning";
          }
        }

        return {
          capturedAtIso: snapshot.captured_at,
          timestamp: formatTime(snapshot.captured_at),
          speed: snapshot.speed_kph,
          temperature: snapshot.temperature_c,
          pressure: snapshot.pressure_bar,
          fuel: snapshot.fuel_level_pct,
          health: snapshot.health_score,
          markerType,
        };
      });
  }, [history, windowMinutes]);

  useEffect(() => {
    if (!data.length) {
      previousDataLengthRef.current = 0;
      setZoomRange(null);
      return;
    }

    const previousLength = previousDataLengthRef.current;
    const nextLength = data.length;

    setZoomRange((previous) => {
      if (!previous) {
        return null;
      }

      const maxIndex = nextLength - 1;
      const width = Math.max(1, previous.endIndex - previous.startIndex);
      let startIndex = previous.startIndex;
      let endIndex = previous.endIndex;

      const wasNearRightEdge = previousLength > 0 && previous.endIndex >= previousLength - 2;
      if (wasNearRightEdge && nextLength !== previousLength) {
        const delta = nextLength - previousLength;
        startIndex += delta;
        endIndex += delta;
      }

      if (endIndex > maxIndex) {
        endIndex = maxIndex;
        startIndex = Math.max(0, endIndex - width);
      }

      if (startIndex < 0) {
        startIndex = 0;
      }

      if (startIndex >= endIndex) {
        endIndex = Math.min(maxIndex, startIndex + width);
      }

      return {
        startIndex,
        endIndex,
      };
    });

    previousDataLengthRef.current = nextLength;
  }, [data.length]);

  const markerPoints = useMemo(
    () => data.filter((point): point is MarkerPoint => point.markerType !== null),
    [data],
  );
  const defaultStartIndex = Math.max(0, data.length - 60);
  const activeStartIndex = zoomRange?.startIndex ?? defaultStartIndex;
  const activeEndIndex = zoomRange?.endIndex ?? Math.max(0, data.length - 1);

  function markerColor(markerType: MarkerType): string {
    if (markerType === "critical") {
      return "hsl(var(--destructive))";
    }
    if (markerType === "warning") {
      return "hsl(var(--health-yellow))";
    }
    return "hsl(var(--chart-voltage))";
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="text-base">Telemetry Trends</CardTitle>
          <div className="flex items-center gap-2">
            {[5, 15, 30].map((minutes) => (
              <Button
                key={minutes}
                variant={windowMinutes === minutes ? "default" : "secondary"}
                size="sm"
                onClick={() => {
                  setWindowMinutes(minutes as WindowPreset);
                  setZoomRange(null);
                }}
              >
                {minutes}m
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs text-muted-foreground">
          Zoom with the range handle below the chart. Event markers in the selected window: {markerPoints.length}.
        </p>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              startIndex={activeStartIndex}
              endIndex={activeEndIndex}
              margin={{ left: 4, right: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(222 30% 18%)" />
              <XAxis
                dataKey="capturedAtIso"
                tickFormatter={formatTime}
                tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }}
                minTickGap={24}
              />
              <YAxis tick={{ fill: "hsl(215 20% 55%)", fontSize: 11 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Tooltip
                labelFormatter={(value) => formatTime(String(value))}
                contentStyle={{
                  background: "hsl(222 47% 9%)",
                  border: "1px solid hsl(222 30% 18%)",
                  borderRadius: 8,
                  color: "hsl(210 40% 92%)",
                }}
              />
              <Line type="monotone" dataKey="speed" stroke="hsl(199 89% 48%)" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="temperature" stroke="hsl(0 72% 51%)" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="pressure" stroke="hsl(142 71% 45%)" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="fuel" stroke="hsl(48 96% 53%)" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="health" stroke="hsl(280 65% 60%)" dot={false} strokeWidth={2} />
              {markerPoints.map((marker) => (
                <ReferenceDot
                  key={`marker-${marker.capturedAtIso}`}
                  x={marker.capturedAtIso}
                  y={marker.health}
                  r={4}
                  fill={markerColor(marker.markerType)}
                  stroke="hsl(var(--background))"
                  strokeWidth={1}
                  ifOverflow="visible"
                />
              ))}
              <Brush
                dataKey="capturedAtIso"
                tickFormatter={formatTime}
                startIndex={activeStartIndex}
                endIndex={activeEndIndex}
                onChange={(range) => {
                  if (typeof range?.startIndex !== "number" || typeof range?.endIndex !== "number") {
                    return;
                  }
                  setZoomRange({
                    startIndex: range.startIndex,
                    endIndex: range.endIndex,
                  });
                }}
                travellerWidth={12}
                height={26}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
