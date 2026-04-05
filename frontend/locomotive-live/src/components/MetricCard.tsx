import { Card, CardContent } from "@/components/ui/card";
import { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: number;
  unit: string;
  icon: LucideIcon;
  colorClass?: string;
  secondaryValue?: string;
}

export default function MetricCard({
  label,
  value,
  unit,
  icon: Icon,
  colorClass = "text-primary",
  secondaryValue,
}: Props) {
  return (
    <Card className="transition-shadow hover:glow-primary">
      <CardContent className="flex items-center gap-4 p-5">
        <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-secondary ${colorClass}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold tabular-nums">{value.toFixed(1)} <span className="text-sm font-normal text-muted-foreground">{unit}</span></p>
          {secondaryValue ? <p className="text-xs text-muted-foreground">{secondaryValue}</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}
