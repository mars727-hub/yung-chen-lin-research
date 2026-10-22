"""Generate deterministic educational synthetic transfer/output data."""

from __future__ import annotations

from pathlib import Path
import csv
import math

import numpy as np


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def make_measurements() -> list[dict[str, object]]:
    rng = np.random.default_rng(20261022)
    rows: list[dict[str, object]] = []
    vg_values = np.arange(0.0, 6.001, 0.25)
    vds_values = np.arange(0.01, 0.101, 0.01)
    stress_values = [0.0, 100.0, 1000.0, 10000.0]
    device_offsets = {"D01": 0.00, "D02": 0.025, "D03": -0.018}
    temperature = 25.0
    for device, vth_offset in device_offsets.items():
        for stress in stress_values:
            drift = 0.055 * math.log10(1.0 + stress / 100.0)
            vth = 2.70 + vth_offset + drift
            # The generated transfer curve is deliberately monotonic, so the
            # default constant-current extraction has a unique crossing.
            for vg in vg_values:
                overdrive = max(vg - vth, 0.0)
                current = 1e-7 + 3.6e-4 * overdrive**1.65
                rows.append(
                    {
                        "device_id": device,
                        "sweep": "transfer",
                        "stress_time_s": stress,
                        "temperature_C": temperature,
                        "Vg_V": round(float(vg), 8),
                        "Vds_V": 0.10,
                        "Id_A": round(float(current), 12),
                        "Ig_A": round(float(1e-9 * (1.0 + 0.2 * vg)), 12),
                        "cycle": int(stress),
                    }
                )
            ron = 0.80 * (1.0 + 0.025 * math.log10(1.0 + stress / 100.0))
            ron *= 1.0 + 0.02 * (vth_offset / 0.025 if vth_offset else 0.0)
            for vds in vds_values:
                # Fixed seed noise is small relative to the linear signal.
                noise = float(rng.normal(0.0, 1.5e-6))
                current = vds / ron + noise
                rows.append(
                    {
                        "device_id": device,
                        "sweep": "output",
                        "stress_time_s": stress,
                        "temperature_C": temperature,
                        "Vg_V": 5.0,
                        "Vds_V": round(float(vds), 8),
                        "Id_A": round(float(current), 12),
                        "Ig_A": round(float(1e-9 * (1.0 + stress / 10000.0)), 12),
                        "cycle": int(stress),
                    }
                )
    return rows


def make_failure_events() -> list[dict[str, object]]:
    # The default file is deliberately full-failure only because fit_weibull
    # refuses to silently exclude right-censored rows.
    complete_times = [120, 180, 245, 310, 380, 470, 590, 760, 930, 1180]
    rows = [
        {"device_id": f"F{i:02d}", "failure_time_s": time, "event_observed": 1}
        for i, time in enumerate(complete_times, start=1)
    ]
    return rows


def make_censored_example() -> list[dict[str, object]]:
    rows = make_failure_events()
    rows.extend(
        [
            {"device_id": "C01", "failure_time_s": 1500, "event_observed": 0},
            {"device_id": "C02", "failure_time_s": 1500, "event_observed": 0},
        ]
    )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    write_csv(DATA / "synthetic_measurements.csv", make_measurements())
    write_csv(DATA / "failure_events.csv", make_failure_events())
    write_csv(DATA / "failure_events_censored_example.csv", make_censored_example())
    print("Wrote deterministic synthetic data to", DATA)

