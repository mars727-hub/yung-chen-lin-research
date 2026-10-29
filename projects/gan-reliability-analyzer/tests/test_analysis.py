import sys
import unittest
from pathlib import Path
import re

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gan_reliability import (  # noqa: E402
    AnalysisError,
    NonMonotonicDataError,
    OutOfRangeError,
    SchemaError,
    add_stress_shifts,
    analyze_measurements,
    extract_ron,
    extract_vth,
    fit_weibull,
    write_delta_vth_plot,
    write_stress_plot,
    write_transfer_plot,
)


class AnalyzerTests(unittest.TestCase):
    def test_vth_linear_interpolation(self):
        curve = pd.DataFrame({"Vg_V": [0.0, 1.0, 2.0], "Id_A": [0.0, 0.5, 1.5]})
        self.assertAlmostEqual(extract_vth(curve, current_threshold_a=1.0), 1.5)

    def test_vth_out_of_range_is_explicit(self):
        curve = pd.DataFrame({"Vg_V": [0.0, 1.0], "Id_A": [0.0, 0.5]})
        with self.assertRaises(OutOfRangeError):
            extract_vth(curve, current_threshold_a=1.0)

    def test_vth_rejects_missing_and_mixed_vds(self):
        missing = pd.DataFrame({"Vg_V": [0.0, 1.0], "Id_A": [0.0, np.nan]})
        with self.assertRaises(SchemaError):
            extract_vth(missing)
        mixed_vds = pd.DataFrame(
            {"Vg_V": [0.0, 1.0, 2.0], "Id_A": [0.0, 0.001, 0.002], "Vds_V": [0.1, 0.1, 0.2]}
        )
        with self.assertRaises(SchemaError):
            extract_vth(mixed_vds)

    def test_vth_nonmonotonic_is_rejected(self):
        curve = pd.DataFrame({"Vg_V": [0.0, 1.0, 2.0], "Id_A": [0.0, 2.0, 1.0]})
        with self.assertRaises(NonMonotonicDataError):
            extract_vth(curve, current_threshold_a=1.0)

    def test_ron_is_inverse_of_known_slope(self):
        vds = np.array([0.01, 0.02, 0.03, 0.04])
        curve = pd.DataFrame({"Vg_V": 5.0, "Vds_V": vds, "Id_A": vds / 2.0 + 0.001})
        result = extract_ron(curve, vds_min_v=0.01, vds_max_v=0.04)
        self.assertAlmostEqual(result["ron_ohm"], 2.0, places=8)
        self.assertAlmostEqual(result["r2"], 1.0, places=8)

    def test_weibull_fit_returns_positive_parameters_and_counts_censoring(self):
        frame = pd.DataFrame(
            {
                "failure_time_s": [10, 20, 40, 80],
                "event_observed": [1, 1, 1, 1],
            }
        )
        result = fit_weibull(frame)
        self.assertEqual(result.n_complete, 4)
        self.assertEqual(result.n_censored, 0)
        self.assertGreater(result.beta, 0.0)
        self.assertGreater(result.eta_s, 0.0)

    def test_weibull_rejects_censored_invalid_flags_and_nonpositive_times(self):
        censored = pd.DataFrame({"failure_time_s": [10, 20, 30], "event_observed": [1, 0, 1]})
        with self.assertRaises(AnalysisError):
            fit_weibull(censored)
        invalid_flag = pd.DataFrame({"failure_time_s": [10, 20, 30], "event_observed": [1, 2, 1]})
        with self.assertRaises(SchemaError):
            fit_weibull(invalid_flag)
        nonpositive = pd.DataFrame({"failure_time_s": [0, 20, 30], "event_observed": [1, 1, 1]})
        with self.assertRaises(SchemaError):
            fit_weibull(nonpositive)

    def test_weibull_scale_invariance(self):
        base = pd.DataFrame({"failure_time_s": [10, 20, 40, 80, 160, 320], "event_observed": [1] * 6})
        fit_base = fit_weibull(base)
        scaled = base.copy()
        scaled["failure_time_s"] *= 10.0
        fit_scaled = fit_weibull(scaled)
        self.assertAlmostEqual(fit_scaled.beta, fit_base.beta, places=10)
        self.assertAlmostEqual(fit_scaled.eta_s, fit_base.eta_s * 10.0, places=8)

    def test_weibull_known_quantile_sample_is_reasonable(self):
        # Quantiles from a Weibull(beta=2, eta=100) distribution; this avoids
        # a random seed while checking the MLE on a broad deterministic sample.
        quantiles = np.linspace(0.001, 0.999, 1000)
        times = 100.0 * (-np.log1p(-quantiles)) ** 0.5
        frame = pd.DataFrame({"failure_time_s": times, "event_observed": 1})
        result = fit_weibull(frame)
        self.assertAlmostEqual(result.beta, 2.0, delta=0.10)
        self.assertAlmostEqual(result.eta_s, 100.0, delta=2.0)

    @staticmethod
    def _metrics(stress_times=(0.0, 10.0)):
        return pd.DataFrame(
            [
                {
                    "device_id": "D1",
                    "stress_time_s": time,
                    "temperature_C": 25.0,
                    "cycle": int(time),
                    "current_threshold_A": 1e-3,
                    "transfer_vds_V": 0.1,
                    "vth_V": 2.0 + time / 100.0,
                    "ron_ohm": 1.0 + time / 100.0,
                    "vg_target_V": 5.0,
                    "vds_min_V": 0.01,
                    "vds_max_V": 0.1,
                }
                for time in stress_times
            ]
        )

    def test_stress_baseline_requires_unique_zero(self):
        with self.assertRaises(SchemaError):
            add_stress_shifts(self._metrics((1.0, 10.0)))
        with self.assertRaises(SchemaError):
            add_stress_shifts(self._metrics((0.0, 0.0, 10.0)))
        shifted = add_stress_shifts(self._metrics((0.0, 10.0)))
        self.assertAlmostEqual(float(shifted.loc[shifted.stress_time_s == 0, "delta_vth_V"].iloc[0]), 0.0)
        self.assertAlmostEqual(float(shifted.loc[shifted.stress_time_s == 10, "delta_vth_V"].iloc[0]), 0.1)

    def test_stress_baseline_isolated_by_temperature(self):
        rows = []
        for temperature, base_vth, base_ron in ((25.0, 2.0, 1.0), (75.0, 3.0, 2.0)):
            for time in (0.0, 10.0):
                rows.append(
                    {
                        "device_id": "D1",
                        "stress_time_s": time,
                        "temperature_C": temperature,
                        "cycle": int(time),
                        "current_threshold_A": 1e-3,
                        "transfer_vds_V": 0.1,
                        "vth_V": base_vth + time / 100.0,
                        "ron_ohm": base_ron + time / 100.0,
                        "vg_target_V": 5.0,
                        "vds_min_V": 0.01,
                        "vds_max_V": 0.1,
                    }
                )
        shifted = add_stress_shifts(pd.DataFrame(rows))
        for temperature, expected_delta in ((25.0, 0.1), (75.0, 0.1)):
            row = shifted[(shifted.temperature_C == temperature) & (shifted.stress_time_s == 10.0)].iloc[0]
            self.assertAlmostEqual(float(row.delta_vth_V), expected_delta)

    def test_analyze_rejects_mixed_cycle_in_one_group(self):
        frame = pd.DataFrame(
            {
                "device_id": ["D1"] * 6,
                "sweep": ["transfer"] * 3 + ["output"] * 3,
                "stress_time_s": [0.0] * 6,
                "temperature_C": [25.0] * 6,
                "Vg_V": [0.0, 1.0, 2.0, 5.0, 5.0, 5.0],
                "Vds_V": [0.1] * 3 + [0.01, 0.02, 0.03],
                "Id_A": [0.0, 0.001, 0.002, 0.005, 0.01, 0.015],
                "Ig_A": [0.0] * 6,
                "cycle": [0, 1, 0, 0, 0, 0],
            }
        )
        with self.assertRaises(SchemaError):
            analyze_measurements(frame)

    def test_plots_use_complete_baseline_and_include_delta_vth(self):
        frame = pd.DataFrame(
            {
                "device_id": ["D1"] * 6,
                "sweep": ["transfer"] * 6,
                "stress_time_s": [0.0] * 3 + [10.0] * 3,
                "temperature_C": [25.0] * 6,
                "Vg_V": [0.0, 1.0, 2.0, 0.0, 1.0, 2.0],
                "Vds_V": [0.1] * 6,
                "Id_A": [0.0, 0.001, 0.002, 0.0, 0.001, 0.002],
                "Ig_A": [0.0] * 6,
                "cycle": [0, 0, 0, 10, 10, 10],
            }
        )
        metrics = self._metrics((0.0, 10.0))
        output_dir = ROOT / "_test_outputs"
        output_dir.mkdir(exist_ok=True)
        transfer_path = output_dir / "transfer.svg"
        stress_path = output_dir / "stress.svg"
        delta_path = output_dir / "delta.svg"
        try:
            write_transfer_plot(frame, transfer_path, current_threshold_a=1e-3)
            write_stress_plot(add_stress_shifts(metrics), stress_path)
            write_delta_vth_plot(add_stress_shifts(metrics), delta_path)
            transfer_svg = transfer_path.read_text(encoding="utf-8")
            first_polyline = re.search(r'<polyline points="([^"]+)"', transfer_svg)
            self.assertIsNotNone(first_polyline)
            self.assertGreaterEqual(len(first_polyline.group(1).split()), 3)
            self.assertTrue(stress_path.exists())
            self.assertIn("ΔVTH", delta_path.read_text(encoding="utf-8"))
        finally:
            for path in (transfer_path, stress_path, delta_path):
                if path.exists():
                    path.unlink()
            if output_dir.exists() and not any(output_dir.iterdir()):
                output_dir.rmdir()


if __name__ == "__main__":
    unittest.main()

