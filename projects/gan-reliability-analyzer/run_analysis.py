"""Command-line entry point for the educational reliability analyzer."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from gan_reliability import (  # noqa: E402
    add_stress_shifts,
    analyze_measurements,
    fit_weibull,
    read_measurement_csv,
    write_delta_vth_plot,
    write_stress_plot,
    write_transfer_plot,
    write_weibull_plot,
    write_weibull_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze synthetic or authorized GaN reliability curves")
    parser.add_argument("--measurement-csv", type=Path, required=True)
    parser.add_argument("--failure-csv", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--current-threshold-a", type=float, default=1e-3)
    parser.add_argument("--ron-vds-min-v", type=float, default=0.01)
    parser.add_argument("--ron-vds-max-v", type=float, default=0.10)
    parser.add_argument("--vg-target-v", type=float, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame = read_measurement_csv(args.measurement_csv)
    metrics = analyze_measurements(
        frame,
        current_threshold_a=args.current_threshold_a,
        vds_min_v=args.ron_vds_min_v,
        vds_max_v=args.ron_vds_max_v,
        vg_target_v=args.vg_target_v,
    )
    metrics = add_stress_shifts(metrics)
    metrics.to_csv(args.output_dir / "summary_metrics.csv", index=False)
    write_transfer_plot(frame, args.output_dir / "transfer_curves.svg", args.current_threshold_a)
    write_stress_plot(metrics, args.output_dir / "stress_metrics.svg")
    write_delta_vth_plot(metrics, args.output_dir / "delta_vth_metrics.svg")
    if args.failure_csv is not None:
        failures = pd.read_csv(args.failure_csv)
        fit = fit_weibull(failures)
        write_weibull_summary(fit, args.output_dir / "weibull_fit.csv")
        write_weibull_plot(failures, args.output_dir / "weibull_probability.svg")
        print(f"Weibull: beta={fit.beta:.4g}, eta={fit.eta_s:.4g} s, complete={fit.n_complete}, censored={fit.n_censored}")
    print(f"Analyzed {len(metrics)} device/stress groups; wrote {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

