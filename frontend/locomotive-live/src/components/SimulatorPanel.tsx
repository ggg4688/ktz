import { useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type { SimulatorControlRequest, SimulatorStatus } from "@/lib/api";

interface Props {
  simulator: SimulatorStatus | null;
  locomotiveId: string;
  canOperate: boolean;
  onStart: (request: SimulatorControlRequest) => Promise<void>;
  onStop: () => Promise<void>;
}

export default function SimulatorPanel({
  simulator,
  locomotiveId,
  canOperate,
  onStart,
  onStop,
}: Props) {
  const [scenario, setScenario] = useState<SimulatorControlRequest["scenario"]>("baseline");
  const [intervalMs, setIntervalMs] = useState(1000);
  const [burstSize, setBurstSize] = useState(1);
  const [loadMultiplier, setLoadMultiplier] = useState(1);
  const [resetState, setResetState] = useState(true);
  const [pending, setPending] = useState(false);

  const handleStart = async () => {
    setPending(true);
    try {
      await onStart({
        scenario,
        interval_ms: intervalMs,
        burst_size: burstSize,
        load_multiplier: loadMultiplier,
        locomotive_id: locomotiveId,
        reset_state: resetState,
      });
    } finally {
      setPending(false);
    }
  };

  const handleStop = async () => {
    setPending(true);
    try {
      await onStop();
    } finally {
      setPending(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Simulator Control</CardTitle>
        <CardDescription>
          Trigger realistic demo scenarios and higher event rates directly from the frontend.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant={simulator?.running ? "default" : "secondary"}>
            {simulator?.running ? "Running" : "Stopped"}
          </Badge>
          <Badge variant="outline">{simulator?.scenario || scenario}</Badge>
          {simulator?.tick !== undefined ? <Badge variant="outline">Tick {simulator.tick}</Badge> : null}
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="space-y-2 text-sm">
            <span className="text-muted-foreground">Scenario</span>
            <select
              value={scenario}
              onChange={(event) => setScenario(event.target.value as SimulatorControlRequest["scenario"])}
              className="flex h-10 w-full rounded-md border border-input bg-secondary/50 px-3 py-2 text-sm"
              disabled={!canOperate || pending}
            >
              <option value="baseline">baseline</option>
              <option value="overheat">overheat</option>
              <option value="pressure_drop">pressure_drop</option>
              <option value="low_fuel">low_fuel</option>
              <option value="mixed_failure">mixed_failure</option>
            </select>
          </label>

          <label className="space-y-2 text-sm">
            <span className="text-muted-foreground">Interval ms</span>
            <Input
              type="number"
              min={100}
              max={10000}
              value={intervalMs}
              onChange={(event) => setIntervalMs(Number(event.target.value))}
              className="bg-secondary/50"
              disabled={!canOperate || pending}
            />
          </label>

          <label className="space-y-2 text-sm">
            <span className="text-muted-foreground">Burst size</span>
            <Input
              type="number"
              min={1}
              max={100}
              value={burstSize}
              onChange={(event) => setBurstSize(Number(event.target.value))}
              className="bg-secondary/50"
              disabled={!canOperate || pending}
            />
          </label>

          <label className="space-y-2 text-sm">
            <span className="text-muted-foreground">Load multiplier</span>
            <Input
              type="number"
              min={0.5}
              max={10}
              step={0.1}
              value={loadMultiplier}
              onChange={(event) => setLoadMultiplier(Number(event.target.value))}
              className="bg-secondary/50"
              disabled={!canOperate || pending}
            />
          </label>
        </div>

        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={resetState}
            onChange={(event) => setResetState(event.target.checked)}
            disabled={!canOperate || pending}
          />
          Reset simulator state before start
        </label>

        <div className="flex flex-wrap gap-3">
          <Button onClick={handleStart} disabled={!canOperate || pending}>
            {pending ? "Submitting..." : "Start scenario"}
          </Button>
          <Button variant="secondary" onClick={handleStop} disabled={!canOperate || pending}>
            Stop simulator
          </Button>
        </div>

        {!canOperate ? (
          <p className="text-sm text-muted-foreground">
            Viewer accounts can monitor simulator output but cannot control it.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
