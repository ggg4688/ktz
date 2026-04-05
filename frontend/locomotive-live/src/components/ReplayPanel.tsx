import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { ReplayResponse, TelemetrySnapshot } from "@/lib/api";

interface Props {
  replay: ReplayResponse | null;
  onRefresh: (minutes?: number, stride?: number) => Promise<void>;
}

interface EventMarker {
  id: string;
  frameIndex: number;
  capturedAt: string;
  label: string;
  source: "auto" | "manual";
}

function buildAutoMarkers(frames: TelemetrySnapshot[]): EventMarker[] {
  const markers: EventMarker[] = [];

  for (let index = 0; index < frames.length; index += 1) {
    const frame = frames[index];
    const previous = index > 0 ? frames[index - 1] : null;

    if (previous && previous.health_category !== frame.health_category) {
      markers.push({
        id: `auto-category-${index}`,
        frameIndex: index,
        capturedAt: frame.captured_at,
        label: `Health changed to ${frame.health_category}`,
        source: "auto",
      });
    }

    if (frame.alerts.length > 0) {
      const firstAlert = frame.alerts[0];
      const suffix = frame.alerts.length > 1 ? ` (+${frame.alerts.length - 1})` : "";
      markers.push({
        id: `auto-alert-${index}`,
        frameIndex: index,
        capturedAt: frame.captured_at,
        label: `${firstAlert.severity.toUpperCase()} ${firstAlert.metric}${suffix}`,
        source: "auto",
      });
    }
  }

  return markers;
}

export default function ReplayPanel({ replay, onRefresh }: Props) {
  const [minutes, setMinutes] = useState(15);
  const [stride, setStride] = useState(2);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [pending, setPending] = useState(false);
  const [note, setNote] = useState("");
  const [manualMarkers, setManualMarkers] = useState<EventMarker[]>([]);

  useEffect(() => {
    setCursor(0);
    setPlaying(false);
    setNote("");
    setManualMarkers([]);
  }, [replay?.frame_count, replay?.locomotive_id]);

  useEffect(() => {
    if (!playing || !replay?.frames.length) {
      return;
    }

    const interval = window.setInterval(() => {
      setCursor((current) => {
        if (!replay.frames.length) {
          return 0;
        }
        if (current >= replay.frames.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 900);

    return () => window.clearInterval(interval);
  }, [playing, replay]);

  const selectedFrame: TelemetrySnapshot | null =
    replay && replay.frames.length > 0 ? replay.frames[Math.min(cursor, replay.frames.length - 1)] : null;

  const autoMarkers = useMemo(() => (replay ? buildAutoMarkers(replay.frames) : []), [replay]);
  const eventMarkers = useMemo(
    () =>
      [...autoMarkers, ...manualMarkers]
        .sort((left, right) => left.frameIndex - right.frameIndex)
        .slice(-24),
    [autoMarkers, manualMarkers],
  );

  const handleRefresh = async () => {
    setPending(true);
    try {
      await onRefresh(minutes, stride);
    } finally {
      setPending(false);
    }
  };

  const addManualMarker = () => {
    if (!selectedFrame || !note.trim()) {
      return;
    }

    setManualMarkers((current) => [
      ...current,
      {
        id: `manual-${Date.now()}`,
        frameIndex: cursor,
        capturedAt: selectedFrame.captured_at,
        label: note.trim(),
        source: "manual",
      },
    ]);
    setNote("");
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Replay</CardTitle>
        <CardDescription>
          Load recent history, navigate frames, and annotate event markers for diagnostics.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <Input
            type="number"
            min={1}
            max={120}
            value={minutes}
            onChange={(event) => setMinutes(Number(event.target.value))}
            className="bg-secondary/50"
            placeholder="Minutes"
          />
          <Input
            type="number"
            min={1}
            max={20}
            value={stride}
            onChange={(event) => setStride(Number(event.target.value))}
            className="bg-secondary/50"
            placeholder="Stride"
          />
          <Button onClick={handleRefresh} disabled={pending}>
            {pending ? "Loading..." : "Load replay"}
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" onClick={() => setPlaying((current) => !current)} disabled={!selectedFrame}>
            {playing ? "Pause" : "Play"}
          </Button>
          <Button
            variant="ghost"
            onClick={() => setCursor((current) => Math.max(0, current - 1))}
            disabled={!selectedFrame || cursor === 0}
          >
            Previous
          </Button>
          <Button
            variant="ghost"
            onClick={() => setCursor((current) => Math.min((replay?.frames.length || 1) - 1, current + 1))}
            disabled={!selectedFrame || cursor >= (replay?.frames.length || 1) - 1}
          >
            Next
          </Button>
          {replay ? <Badge variant="outline">{replay.frame_count} frames</Badge> : null}
          <Badge variant="outline">{eventMarkers.length} markers</Badge>
        </div>

        {replay?.frames.length ? (
          <>
            <input
              type="range"
              min={0}
              max={Math.max(replay.frames.length - 1, 0)}
              value={cursor}
              onChange={(event) => setCursor(Number(event.target.value))}
              className="w-full accent-[hsl(var(--primary))]"
            />
            {selectedFrame ? (
              <div className="grid gap-3 md:grid-cols-4">
                <div className="rounded-xl border border-border/80 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Captured</p>
                  <p className="mt-2 font-medium">{new Date(selectedFrame.captured_at).toLocaleTimeString()}</p>
                </div>
                <div className="rounded-xl border border-border/80 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Health</p>
                  <p className="mt-2 font-medium">{selectedFrame.health_score.toFixed(1)}</p>
                </div>
                <div className="rounded-xl border border-border/80 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Scenario</p>
                  <p className="mt-2 font-medium">{selectedFrame.scenario_tag || "baseline"}</p>
                </div>
                <div className="rounded-xl border border-border/80 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Alerts</p>
                  <p className="mt-2 font-medium">{selectedFrame.alerts.length}</p>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">No replay loaded yet.</p>
        )}

        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
          <Input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Add marker note for the selected frame"
            className="bg-secondary/50"
            disabled={!selectedFrame}
          />
          <Button onClick={addManualMarker} disabled={!selectedFrame || !note.trim()}>
            Add marker
          </Button>
        </div>

        <div className="space-y-2 rounded-xl border border-border/80 bg-secondary/20 p-3">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Event markers</p>
          {!eventMarkers.length ? (
            <p className="text-sm text-muted-foreground">No markers yet.</p>
          ) : (
            eventMarkers.map((marker) => (
              <div key={marker.id} className="flex items-center justify-between gap-3 rounded-lg border p-2">
                <div>
                  <p className="text-sm">{marker.label}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(marker.capturedAt).toLocaleTimeString()} | frame {marker.frameIndex + 1}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={marker.source === "auto" ? "secondary" : "default"}>{marker.source}</Badge>
                  <Button variant="ghost" size="sm" onClick={() => setCursor(marker.frameIndex)}>
                    Jump
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
