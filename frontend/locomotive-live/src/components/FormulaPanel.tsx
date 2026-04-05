import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { FactorContribution, HealthModelConfig } from "@/lib/api";

interface Props {
  formula: HealthModelConfig | null;
  topFactors: FactorContribution[];
}

export default function FormulaPanel({ formula, topFactors }: Props) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-base">Health Logic</CardTitle>
        <CardDescription>
          Transparent formula, category thresholds, and current strongest degradation factors.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {formula ? (
          <>
            <div className="rounded-xl border border-border/80 bg-secondary/30 p-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <Badge variant="secondary">Version {formula.health_model_version}</Badge>
                <span className="text-xs text-muted-foreground">Retention {formula.retention_hours}h</span>
              </div>
              <p className="text-sm leading-6 text-muted-foreground">{formula.formula}</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-border/80 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Categories</p>
                <p className="mt-2 text-sm">Normal from {formula.categories.normal_min}</p>
                <p className="text-sm">Attention from {formula.categories.attention_min}</p>
                <p className="text-sm">Penalty cap {formula.alert_penalty_cap}</p>
              </div>
              <div className="rounded-xl border border-border/80 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Smoothing</p>
                <p className="mt-2 text-sm">Alpha {formula.smoothing.alpha}</p>
                <p className="text-sm">Warning penalty {formula.severity_penalties.warning}</p>
                <p className="text-sm">Critical penalty {formula.severity_penalties.critical}</p>
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Metric weights</p>
              <div className="grid gap-3 md:grid-cols-2">
                {Object.entries(formula.metrics).map(([metricName, metricConfig]) => (
                  <div key={metricName} className="rounded-xl border border-border/80 bg-secondary/25 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium">{metricConfig.label}</p>
                      <Badge variant="outline">{metricConfig.weight}</Badge>
                    </div>
                    <p className="mt-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                      {metricName.replaceAll("_", " ")}
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Direction: {metricConfig.direction}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Current top factors</p>
              {topFactors.length === 0 ? (
                <p className="text-sm text-muted-foreground">No degradation factors yet.</p>
              ) : (
                topFactors.map((factor) => (
                  <div key={factor.metric} className="rounded-xl border border-border/80 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium">{factor.label}</p>
                      <Badge variant="secondary">{factor.score_impact.toFixed(1)} pts</Badge>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Value {factor.current_value.toFixed(1)} | weight {factor.weight} | penalty {factor.penalty}
                    </p>
                  </div>
                ))
              )}
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Formula config is not available yet.</p>
        )}
      </CardContent>
    </Card>
  );
}
