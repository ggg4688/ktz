import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Props {
  distanceKm: number | null | undefined;
  speedKph: number | null | undefined;
}

interface RouteSection {
  id: string;
  name: string;
  fromKm: number;
  toKm: number;
  speedLimitKph: number;
}

const ROUTE_SECTIONS: RouteSection[] = [
  { id: "depot", name: "Depot", fromKm: 0, toKm: 6, speedLimitKph: 40 },
  { id: "urban", name: "Urban corridor", fromKm: 6, toKm: 18, speedLimitKph: 70 },
  { id: "bridge", name: "Bridge zone", fromKm: 18, toKm: 27, speedLimitKph: 55 },
  { id: "open", name: "Open line", fromKm: 27, toKm: 52, speedLimitKph: 110 },
  { id: "junction", name: "Junction", fromKm: 52, toKm: 66, speedLimitKph: 65 },
  { id: "terminal", name: "Terminal approach", fromKm: 66, toKm: 80, speedLimitKph: 45 },
];

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

export default function RouteSectionMap({ distanceKm, speedKph }: Props) {
  const totalDistance = ROUTE_SECTIONS[ROUTE_SECTIONS.length - 1].toKm;
  const normalizedDistance = clamp(distanceKm ?? 0, 0, totalDistance);
  const normalizedSpeed = Math.max(0, speedKph ?? 0);
  const progressPct = (normalizedDistance / totalDistance) * 100;

  const currentSection =
    ROUTE_SECTIONS.find((section) => normalizedDistance >= section.fromKm && normalizedDistance <= section.toKm) ||
    ROUTE_SECTIONS[ROUTE_SECTIONS.length - 1];

  const overspeed = normalizedSpeed > currentSection.speedLimitKph;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Route Section Map</CardTitle>
        <CardDescription>
          Simplified track scheme with current position and active section speed limit.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-xl border border-border/80 bg-secondary/20 p-4">
          <svg viewBox="0 0 1000 90" className="h-20 w-full">
            {ROUTE_SECTIONS.map((section) => {
              const start = (section.fromKm / totalDistance) * 1000;
              const end = (section.toKm / totalDistance) * 1000;
              const width = end - start;
              const isCurrent = section.id === currentSection.id;

              return (
                <g key={section.id}>
                  <rect
                    x={start}
                    y={34}
                    width={width}
                    height={22}
                    rx={6}
                    className={isCurrent ? "fill-primary/40" : "fill-secondary"}
                  />
                  <line x1={start} y1={65} x2={start} y2={78} className="stroke-border" strokeWidth={2} />
                  <text
                    x={start + width / 2}
                    y={22}
                    className="fill-muted-foreground text-[10px]"
                    textAnchor="middle"
                  >
                    {section.speedLimitKph} km/h
                  </text>
                </g>
              );
            })}
            <line x1={1000} y1={65} x2={1000} y2={78} className="stroke-border" strokeWidth={2} />
            <circle
              cx={(progressPct / 100) * 1000}
              cy={45}
              r={8}
              className={overspeed ? "fill-destructive" : "fill-primary"}
            />
          </svg>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>Position {normalizedDistance.toFixed(2)} km</span>
            <span>|</span>
            <span>Current section {currentSection.name}</span>
            <span>|</span>
            <span>Limit {currentSection.speedLimitKph} km/h</span>
          </div>
        </div>

        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {ROUTE_SECTIONS.map((section) => {
            const isCurrent = section.id === currentSection.id;
            const sectionOverspeed = isCurrent && overspeed;

            return (
              <div
                key={section.id}
                className={`rounded-lg border p-3 ${
                  isCurrent ? "border-primary/60 bg-primary/10" : "border-border/70 bg-secondary/25"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium">{section.name}</p>
                  <Badge variant={sectionOverspeed ? "destructive" : isCurrent ? "default" : "secondary"}>
                    {section.speedLimitKph} km/h
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  km {section.fromKm} - {section.toKm}
                </p>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
