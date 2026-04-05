import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { RecommendationItem } from "@/lib/api";

interface Props {
  recommendations: RecommendationItem[];
}

export default function RecommendationsPanel({ recommendations }: Props) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Recommendations</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {recommendations.length === 0 ? (
          <p className="text-sm text-muted-foreground">No recommendations at the moment.</p>
        ) : null}

        {recommendations.map((item) => (
          <div key={item.code} className="rounded-lg border border-border/80 bg-secondary/35 p-3">
            <div className="mb-2 flex items-center justify-between gap-3">
              <Badge variant={item.priority === 1 ? "destructive" : "secondary"}>Priority {item.priority}</Badge>
              <span className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{item.code}</span>
            </div>
            <p className="text-sm leading-6">{item.message}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
