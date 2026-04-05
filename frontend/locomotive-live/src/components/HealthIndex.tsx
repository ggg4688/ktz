interface Props {
  value: number;
  category?: "normal" | "attention" | "critical";
  capturedAt?: string | null;
}

export default function HealthIndex({ value, category, capturedAt }: Props) {
  const v = Math.round(value);
  const tier =
    category === "critical"
      ? "red"
      : category === "attention"
        ? "yellow"
        : category === "normal"
          ? "green"
          : v >= 80
            ? "green"
            : v >= 50
              ? "yellow"
              : "red";

  const colorClass = {
    green: "health-green",
    yellow: "health-yellow",
    red: "health-red",
  }[tier];

  const bgClass = {
    green: "bg-health-green border-health-green glow-green",
    yellow: "bg-health-yellow border-health-yellow glow-yellow",
    red: "bg-health-red border-health-red glow-red",
  }[tier];

  return (
    <div className={`flex min-h-[260px] flex-col items-center justify-center rounded-2xl border p-8 ${bgClass}`}>
      <span className="text-sm font-medium text-muted-foreground">Health Index</span>
      <span className={`text-7xl font-bold tabular-nums ${colorClass}`}>{v}</span>
      <span className="mt-1 text-xs text-muted-foreground uppercase tracking-[0.24em]">{category || tier}</span>
      {capturedAt && (
        <span className="mt-4 text-xs text-muted-foreground">
          Last update: {new Date(capturedAt).toLocaleTimeString()}
        </span>
      )}
    </div>
  );
}
