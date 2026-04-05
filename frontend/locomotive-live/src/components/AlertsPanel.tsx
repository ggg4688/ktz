import type { AlertItem } from "@/lib/api";
import { AlertTriangle, AlertCircle, Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Props {
  alerts: AlertItem[];
  capturedAt?: string | null;
}

const icons = {
  critical: AlertTriangle,
  warning: AlertCircle,
  info: Info,
};

const styles = {
  critical: "border-health-red bg-health-red health-red",
  warning: "border-health-yellow bg-health-yellow health-yellow",
  info: "border-border bg-secondary text-muted-foreground",
};

export default function AlertsPanel({ alerts, capturedAt }: Props) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Active Alerts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {alerts.length === 0 && <p className="text-sm text-muted-foreground">No active alerts</p>}
        {alerts.map(a => {
          const Icon = icons[a.severity] || Info;
          return (
            <div key={a.code} className={`space-y-2 rounded-lg border p-3 ${styles[a.severity] || styles.info}`}>
              <div className="flex items-center gap-3">
                <Icon className="h-4 w-4 shrink-0" />
                <span className="text-sm font-medium">{a.message}</span>
              </div>
              <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                <Badge variant={a.severity === "critical" ? "destructive" : "secondary"}>{a.metric}</Badge>
                {capturedAt ? <span>{new Date(capturedAt).toLocaleTimeString()}</span> : null}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
