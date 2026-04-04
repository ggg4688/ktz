import unittest

from app.scoring import calculate_health, describe_formula


CONFIG = {
    "retention_hours": 72,
    "smoothing": {"alpha": 0.35},
    "alert_penalty_cap": 35,
    "severity_penalties": {"warning": 8, "critical": 18},
    "categories": {"normal_min": 80, "attention_min": 55},
    "metrics": {
        "temperature_c": {
            "label": "Engine temperature",
            "weight": 0.34,
            "direction": "high_only",
            "ideal_max": 90,
            "safe_max": 110,
            "warning_high": 95,
            "critical_high": 103,
        },
        "pressure_bar": {
            "label": "Main pressure",
            "weight": 0.26,
            "direction": "range",
            "ideal_min": 5.5,
            "ideal_max": 7.5,
            "safe_min": 3.0,
            "safe_max": 9.5,
            "warning_low": 4.5,
            "critical_low": 3.5,
            "warning_high": 8.2,
            "critical_high": 9.0,
        },
        "fuel_level_pct": {
            "label": "Fuel reserve",
            "weight": 0.2,
            "direction": "low_only",
            "ideal_min": 35,
            "safe_min": 8,
            "warning_low": 22,
            "critical_low": 12,
        },
        "speed_kph": {
            "label": "Speed",
            "weight": 0.2,
            "direction": "high_only",
            "ideal_max": 100,
            "safe_max": 130,
            "warning_high": 112,
            "critical_high": 124,
        },
    },
}


class ScoringTests(unittest.TestCase):
    def test_healthy_values_stay_normal(self) -> None:
        result = calculate_health(
            {
                "temperature_c": 84,
                "pressure_bar": 6.4,
                "fuel_level_pct": 68,
                "speed_kph": 86,
            },
            CONFIG,
        )

        self.assertEqual(result.category, "normal")
        self.assertGreater(result.score, 95)
        self.assertEqual(result.alerts, [])

    def test_critical_temperature_and_low_fuel_drop_score(self) -> None:
        result = calculate_health(
            {
                "temperature_c": 108,
                "pressure_bar": 4.0,
                "fuel_level_pct": 9,
                "speed_kph": 118,
            },
            CONFIG,
        )

        self.assertEqual(result.category, "critical")
        self.assertLess(result.score, 45)
        self.assertTrue(any(alert.metric == "temperature_c" and alert.severity == "critical" for alert in result.alerts))
        self.assertTrue(any(alert.metric == "fuel_level_pct" and alert.severity == "critical" for alert in result.alerts))
        self.assertEqual(result.top_factors[0].metric, "temperature_c")

    def test_formula_description_is_transparent(self) -> None:
        description = describe_formula(CONFIG)

        self.assertIn("formula", description)
        self.assertIn("metrics", description)
        self.assertEqual(description["metrics"]["temperature_c"]["weight"], 0.34)


if __name__ == "__main__":
    unittest.main()
