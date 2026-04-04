from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import AlertItem, FactorContribution, RecommendationItem

METRIC_FIELDS = ("temperature_c", "pressure_bar", "fuel_level_pct", "speed_kph")

FORMULA_TEXT = (
    "score = 100 - sum(metric_penalty * metric_weight * 100)"
    " - min(alert_penalty_cap, sum(active_alert_penalties))"
)

_RECOMMENDATION_MAP = {
    "temperature_c": {
        "warning": "Reduce traction load and inspect the cooling circuit.",
        "critical": "Reduce load immediately and inspect engine cooling before continuing the run.",
    },
    "pressure_bar": {
        "warning": "Check the pressure line and validate compressor stability.",
        "critical": "Pressure is outside the safe corridor. Inspect the pneumatic subsystem immediately.",
    },
    "fuel_level_pct": {
        "warning": "Plan refueling before the next route section.",
        "critical": "Fuel reserve is critically low. Refuel or stop the scenario to avoid shutdown.",
    },
    "speed_kph": {
        "warning": "Reduce speed and keep monitoring thermal and pressure behavior.",
        "critical": "Reduce speed immediately and verify whether the locomotive can keep operating safely.",
    },
}


@dataclass(slots=True)
class HealthComputation:
    score: float
    category: str
    alert_penalty: float
    formula: str
    top_factors: list[FactorContribution]
    alerts: list[AlertItem]
    recommendations: list[RecommendationItem]


def validate_health_config(config: dict[str, Any]) -> None:
    metrics = config.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("config.metrics must be an object")

    missing = [metric for metric in METRIC_FIELDS if metric not in metrics]
    if missing:
        raise ValueError(f"missing metric configs: {', '.join(missing)}")

    total_weight = 0.0
    for metric_name in METRIC_FIELDS:
        metric_cfg = metrics[metric_name]
        if metric_cfg.get("direction") not in {"range", "low_only", "high_only"}:
            raise ValueError(f"{metric_name}: unsupported direction")
        weight = float(metric_cfg.get("weight", 0))
        if weight <= 0:
            raise ValueError(f"{metric_name}: weight must be positive")
        total_weight += weight

    if not 0.8 <= total_weight <= 1.2:
        raise ValueError("metric weights should sum to roughly 1.0")

    categories = config.get("categories", {})
    if float(categories.get("normal_min", 0)) <= float(categories.get("attention_min", 0)):
        raise ValueError("categories.normal_min must be greater than categories.attention_min")

    for metric_name in METRIC_FIELDS:
        metric_cfg = metrics[metric_name]
        direction = metric_cfg["direction"]
        if direction == "range":
            _metric_penalty((float(metric_cfg["ideal_min"]) + float(metric_cfg["ideal_max"])) / 2, metric_cfg)
        elif direction == "low_only":
            _metric_penalty(float(metric_cfg["ideal_min"]) + 5, metric_cfg)
        else:
            _metric_penalty(float(metric_cfg["ideal_max"]) - 5, metric_cfg)


def describe_formula(config: dict[str, Any]) -> dict[str, Any]:
    validate_health_config(config)
    return {
        "formula": FORMULA_TEXT,
        "retention_hours": config["retention_hours"],
        "smoothing": config["smoothing"],
        "categories": config["categories"],
        "alert_penalty_cap": config["alert_penalty_cap"],
        "severity_penalties": config["severity_penalties"],
        "metrics": config["metrics"],
    }


def calculate_health(values: dict[str, float], config: dict[str, Any]) -> HealthComputation:
    validate_health_config(config)
    metrics = config["metrics"]
    contributions: list[FactorContribution] = []

    for metric_name in METRIC_FIELDS:
        metric_cfg = metrics[metric_name]
        current_value = float(values[metric_name])
        penalty = round(_metric_penalty(current_value, metric_cfg), 4)
        score_impact = round(penalty * float(metric_cfg["weight"]) * 100, 2)
        contributions.append(
            FactorContribution(
                metric=metric_name,
                label=metric_cfg["label"],
                weight=float(metric_cfg["weight"]),
                penalty=penalty,
                score_impact=score_impact,
                current_value=round(current_value, 2),
            )
        )

    alerts = _build_alerts(values, metrics)
    severity_penalties = config["severity_penalties"]
    raw_alert_penalty = sum(float(severity_penalties[alert.severity]) for alert in alerts)
    alert_penalty = round(min(float(config["alert_penalty_cap"]), raw_alert_penalty), 2)

    base_score = 100 - sum(item.score_impact for item in contributions) - alert_penalty
    final_score = round(max(0.0, min(100.0, base_score)), 2)

    categories = config["categories"]
    normal_min = float(categories["normal_min"])
    attention_min = float(categories["attention_min"])
    if final_score >= normal_min:
        category = "normal"
    elif final_score >= attention_min:
        category = "attention"
    else:
        category = "critical"

    top_factors = sorted(contributions, key=lambda item: item.score_impact, reverse=True)[:5]
    recommendations = _build_recommendations(alerts, top_factors, category)

    return HealthComputation(
        score=final_score,
        category=category,
        alert_penalty=alert_penalty,
        formula=FORMULA_TEXT,
        top_factors=top_factors,
        alerts=alerts,
        recommendations=recommendations,
    )


def _metric_penalty(value: float, metric_cfg: dict[str, Any]) -> float:
    direction = metric_cfg["direction"]
    safe_min = float(metric_cfg.get("safe_min", metric_cfg.get("ideal_min", value)))
    safe_max = float(metric_cfg.get("safe_max", metric_cfg.get("ideal_max", value)))
    ideal_min = float(metric_cfg.get("ideal_min", safe_min))
    ideal_max = float(metric_cfg.get("ideal_max", safe_max))

    if direction == "low_only":
        if value >= ideal_min:
            return 0.0
        if value <= safe_min:
            return 1.0
        return _clamp((ideal_min - value) / max(ideal_min - safe_min, 0.0001))

    if direction == "high_only":
        if value <= ideal_max:
            return 0.0
        if value >= safe_max:
            return 1.0
        return _clamp((value - ideal_max) / max(safe_max - ideal_max, 0.0001))

    if ideal_min <= value <= ideal_max:
        return 0.0
    if value < ideal_min:
        if value <= safe_min:
            return 1.0
        return _clamp((ideal_min - value) / max(ideal_min - safe_min, 0.0001))
    if value >= safe_max:
        return 1.0
    return _clamp((value - ideal_max) / max(safe_max - ideal_max, 0.0001))


def _build_alerts(values: dict[str, float], metrics: dict[str, dict[str, Any]]) -> list[AlertItem]:
    items: list[AlertItem] = []

    for metric_name in METRIC_FIELDS:
        metric_cfg = metrics[metric_name]
        label = metric_cfg["label"]
        value = round(float(values[metric_name]), 2)

        critical_high = metric_cfg.get("critical_high")
        critical_low = metric_cfg.get("critical_low")
        warning_high = metric_cfg.get("warning_high")
        warning_low = metric_cfg.get("warning_low")

        if critical_high is not None and value >= float(critical_high):
            items.append(_alert(metric_name, label, value, "critical", "above", float(critical_high)))
            continue
        if critical_low is not None and value <= float(critical_low):
            items.append(_alert(metric_name, label, value, "critical", "below", float(critical_low)))
            continue
        if warning_high is not None and value >= float(warning_high):
            items.append(_alert(metric_name, label, value, "warning", "above", float(warning_high)))
            continue
        if warning_low is not None and value <= float(warning_low):
            items.append(_alert(metric_name, label, value, "warning", "below", float(warning_low)))

    return items


def _alert(metric: str, label: str, value: float, severity: str, relation: str, threshold: float) -> AlertItem:
    recommendation = _RECOMMENDATION_MAP[metric][severity]
    return AlertItem(
        code=f"{metric}_{severity}",
        severity=severity,
        metric=metric,
        message=f"{label} is {relation} the {severity} threshold ({value} vs {threshold}).",
        recommendation=recommendation,
    )


def _build_recommendations(
    alerts: list[AlertItem],
    top_factors: list[FactorContribution],
    category: str,
) -> list[RecommendationItem]:
    items: list[RecommendationItem] = []

    for alert in sorted(alerts, key=lambda item: (0 if item.severity == "critical" else 1, item.metric)):
        priority = 1 if alert.severity == "critical" else 2
        items.append(RecommendationItem(code=alert.code, priority=priority, message=alert.recommendation))

    if not alerts and top_factors and top_factors[0].score_impact > 0:
        factor = top_factors[0]
        items.append(
            RecommendationItem(
                code=f"{factor.metric}_watch",
                priority=3,
                message=(
                    f"Watch {factor.label.lower()}. It is currently the strongest contributor "
                    f"to health score degradation ({factor.score_impact:.1f} points)."
                ),
            )
        )

    if not items:
        message = (
            "Operating window is stable. Keep monitoring the live stream."
            if category == "normal"
            else "No direct alert is active, but the locomotive health is trending away from nominal behavior."
        )
        items.append(RecommendationItem(code="monitoring", priority=3, message=message))

    unique_items: list[RecommendationItem] = []
    seen: set[str] = set()
    for item in items:
        if item.code in seen:
            continue
        seen.add(item.code)
        unique_items.append(item)
        if len(unique_items) == 3:
            break
    return unique_items


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
