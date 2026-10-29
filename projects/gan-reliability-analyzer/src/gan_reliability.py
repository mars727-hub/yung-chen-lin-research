"""Small, dependency-light helpers for an educational GaN reliability workflow.

The functions deliberately validate units and curve shape.  They operate on
synthetic or user-authorized CSV data only; no claim is made about WLab data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
import html
import math

import numpy as np
import pandas as pd


class AnalysisError(ValueError):
    """Base class for user-facing data or analysis errors."""


class SchemaError(AnalysisError):
    """Input CSV is missing columns or contains unsupported values."""


class OutOfRangeError(AnalysisError):
    """Requested threshold/window is outside the supplied curve."""


class NonMonotonicDataError(AnalysisError):
    """A transfer curve has an ambiguous threshold crossing."""


MEASUREMENT_COLUMNS = (
    "device_id",
    "sweep",
    "stress_time_s",
    "temperature_C",
    "Vg_V",
    "Vds_V",
    "Id_A",
    "Ig_A",
    "cycle",
)
GROUP_COLUMNS = ["device_id", "stress_time_s", "temperature_C"]


def read_measurement_csv(path: str | Path) -> pd.DataFrame:
    """Read and validate the long-form transfer/output measurement CSV."""

    frame = pd.read_csv(path)
    missing = [column for column in MEASUREMENT_COLUMNS if column not in frame.columns]
    if missing:
        raise SchemaError(f"measurement CSV missing columns: {', '.join(missing)}")
    if frame.empty:
        raise SchemaError("measurement CSV is empty")
    frame = frame.copy()
    if frame["sweep"].isna().any() or frame["sweep"].astype(str).str.strip().eq("").any() or not set(frame["sweep"].dropna().unique()).issubset({"transfer", "output"}):
        raise SchemaError("sweep must contain only transfer or output")
    for column in MEASUREMENT_COLUMNS[2:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    numeric = list(MEASUREMENT_COLUMNS[2:])
    if frame[numeric].isna().any().any():
        bad = [column for column in numeric if frame[column].isna().any()]
        raise SchemaError(f"non-numeric or missing values in: {', '.join(bad)}")
    if not np.isfinite(frame[numeric].to_numpy(dtype=float)).all():
        raise SchemaError("measurement numeric values must all be finite")
    if (frame["stress_time_s"] < 0).any():
        raise SchemaError("stress_time_s must be non-negative")
    if (frame["temperature_C"] < -273.15).any():
        raise SchemaError("temperature_C is below absolute zero")
    if frame["device_id"].isna().any() or frame["device_id"].astype(str).str.strip().eq("").any():
        raise SchemaError("device_id cannot be missing")
    return frame


def _linear_crossings(x: np.ndarray, y: np.ndarray, threshold: float) -> list[float]:
    crossings: list[float] = []
    for x0, x1, y0, y1 in zip(x[:-1], x[1:], y[:-1], y[1:]):
        if y0 == threshold:
            crossings.append(float(x0))
        if (y0 - threshold) * (y1 - threshold) < 0:
            if y1 == y0:
                continue
            fraction = (threshold - y0) / (y1 - y0)
            crossings.append(float(x0 + fraction * (x1 - x0)))
        elif y1 == threshold:
            crossings.append(float(x1))
    # Duplicate endpoint crossings can occur when a point equals the threshold.
    return sorted({round(value, 14) for value in crossings})


def extract_vth(
    curve: pd.DataFrame,
    current_threshold_a: float = 1e-3,
    monotonic_tolerance_a: float = 1e-12,
    vds_target_v: float | None = None,
    vds_tolerance_v: float = 0.0,
) -> float:
    """Extract VTH from one transfer curve by linear interpolation.

    ``curve`` must contain ``Vg_V`` and ``Id_A``.  A decreasing segment is
    rejected because it can make the threshold crossing ambiguous.  A curve
    that never reaches the specified current raises :class:`OutOfRangeError`.
    """

    if current_threshold_a <= 0:
        raise ValueError("current_threshold_a must be positive and expressed in A")
    if not {"Vg_V", "Id_A"}.issubset(curve.columns):
        raise SchemaError("transfer curve requires Vg_V and Id_A")
    required = ["Vg_V", "Id_A"] + (["Vds_V"] if "Vds_V" in curve.columns else [])
    if curve[required].isna().any().any() or not np.isfinite(curve[required].to_numpy(dtype=float)).all():
        raise SchemaError("transfer curve contains missing or non-finite values")
    if "Vds_V" in curve.columns:
        vds_values = curve["Vds_V"].to_numpy(dtype=float)
        if vds_target_v is not None and not np.isclose(vds_values, vds_target_v, rtol=0.0, atol=vds_tolerance_v).all():
            raise SchemaError("transfer curve Vds_V does not match the requested fixed VDS")
        if vds_target_v is None and len(np.unique(vds_values)) != 1:
            raise SchemaError("transfer curve must use one fixed Vds_V")
    selected = curve[["Vg_V", "Id_A"]].sort_values("Vg_V")
    if len(selected) < 2:
        raise OutOfRangeError("at least two transfer points are required")
    x = selected["Vg_V"].to_numpy(dtype=float)
    y = selected["Id_A"].to_numpy(dtype=float)
    if np.any(np.diff(x) <= 0):
        raise SchemaError("Vg_V values must be strictly increasing after sorting")
    if np.any(np.diff(y) < -abs(monotonic_tolerance_a)):
        raise NonMonotonicDataError("Id_A decreases along the transfer sweep")
    crossings = _linear_crossings(x, y, float(current_threshold_a))
    if not crossings:
        raise OutOfRangeError(
            f"current threshold {current_threshold_a:g} A is outside "
            f"Id range [{y.min():g}, {y.max():g}] A"
        )
    if len(crossings) > 1:
        raise NonMonotonicDataError(
            f"threshold has {len(crossings)} crossings; choose a validated monotonic sweep"
        )
    return crossings[0]


def _r_squared(y: np.ndarray, prediction: np.ndarray) -> float:
    residual = float(np.sum((y - prediction) ** 2))
    total = float(np.sum((y - np.mean(y)) ** 2))
    if total <= 0:
        return float("nan")
    return 1.0 - residual / total


def extract_ron(
    curve: pd.DataFrame,
    vds_min_v: float = 0.01,
    vds_max_v: float = 0.10,
    vg_target_v: float | None = None,
    vg_tolerance_v: float = 1e-9,
) -> dict[str, float]:
    """Estimate low-field RON from ``ID`` versus ``VDS`` by linear regression."""

    if vds_min_v < 0 or vds_max_v <= vds_min_v:
        raise ValueError("RON window must satisfy 0 <= vds_min_v < vds_max_v")
    needed = {"Vds_V", "Id_A", "Vg_V"}
    if not needed.issubset(curve.columns):
        raise SchemaError("output curve requires Vds_V, Id_A and Vg_V")
    required = ["Vds_V", "Id_A", "Vg_V"]
    if curve[required].isna().any().any() or not np.isfinite(curve[required].to_numpy(dtype=float)).all():
        raise SchemaError("output curve contains missing or non-finite values")
    selected = curve.copy()
    if vg_target_v is None:
        vg_target_v = float(selected["Vg_V"].median())
    selected = selected[np.isclose(selected["Vg_V"], vg_target_v, rtol=0.0, atol=vg_tolerance_v)]
    selected = selected[selected["Vds_V"].between(vds_min_v, vds_max_v)]
    selected = selected[["Vds_V", "Id_A"]].sort_values("Vds_V")
    if len(selected) < 2:
        raise OutOfRangeError("RON window has fewer than two output points")
    vds = selected["Vds_V"].to_numpy(dtype=float)
    current = selected["Id_A"].to_numpy(dtype=float)
    if np.any(np.diff(vds) <= 0):
        raise SchemaError("Vds_V values must be strictly increasing in the RON window")
    design = np.column_stack([vds, np.ones_like(vds)])
    slope, intercept = np.linalg.lstsq(design, current, rcond=None)[0]
    prediction = slope * vds + intercept
    if not np.isfinite(slope) or slope <= 0:
        raise AnalysisError(f"RON regression slope must be positive; got {slope!r}")
    return {
        "ron_ohm": float(1.0 / slope),
        "slope_A_per_V": float(slope),
        "intercept_A": float(intercept),
        "r2": float(_r_squared(current, prediction)),
        "n_points": float(len(selected)),
        "vg_target_V": float(vg_target_v),
        "vds_min_V": float(vds_min_v),
        "vds_max_V": float(vds_max_v),
    }


def analyze_measurements(
    frame: pd.DataFrame,
    current_threshold_a: float = 1e-3,
    vds_min_v: float = 0.01,
    vds_max_v: float = 0.10,
    vg_target_v: float | None = None,
) -> pd.DataFrame:
    """Extract VTH and RON for each device/stress/temperature group."""

    records: list[dict[str, float | str]] = []
    missing = [column for column in MEASUREMENT_COLUMNS if column not in frame.columns]
    if missing:
        raise SchemaError(f"measurement frame missing columns: {', '.join(missing)}")
    numeric = list(MEASUREMENT_COLUMNS[2:])
    if frame.empty or frame[numeric].isna().any().any() or not np.isfinite(frame[numeric].to_numpy(dtype=float)).all():
        raise SchemaError("measurement frame cannot contain empty or non-finite values")
    for keys, group in frame.groupby(GROUP_COLUMNS, sort=True, dropna=False):
        device_id, stress_time, temperature = keys
        if group["cycle"].nunique(dropna=False) != 1:
            raise SchemaError("one device/stress/temperature group cannot mix cycle values")
        transfer = group[group["sweep"] == "transfer"]
        output = group[group["sweep"] == "output"]
        vth = extract_vth(transfer, current_threshold_a=current_threshold_a)
        transfer_vds = float(transfer["Vds_V"].iloc[0])
        ron = extract_ron(
            output,
            vds_min_v=vds_min_v,
            vds_max_v=vds_max_v,
            vg_target_v=vg_target_v,
        )
        records.append(
            {
                "device_id": str(device_id),
                "stress_time_s": float(stress_time),
                "temperature_C": float(temperature),
                "cycle": int(group["cycle"].iloc[0]),
                "current_threshold_A": float(current_threshold_a),
                "transfer_vds_V": transfer_vds,
                "vth_V": float(vth),
                **ron,
            }
        )
    if not records:
        raise SchemaError("no complete transfer/output groups found")
    return pd.DataFrame.from_records(records).sort_values(GROUP_COLUMNS).reset_index(drop=True)


def add_stress_shifts(metrics: pd.DataFrame) -> pd.DataFrame:
    """Add baseline shifts, requiring one unique t=0 row per test condition."""

    required = {"device_id", "stress_time_s", "vth_V", "ron_ohm"}
    if not required.issubset(metrics.columns):
        raise SchemaError(f"metrics missing columns: {', '.join(sorted(required - set(metrics.columns)))}")
    result = metrics.copy()
    if result.empty or result.isna().any().any():
        raise SchemaError("metrics cannot contain empty values")
    condition_columns = ["device_id", "temperature_C", "vg_target_V", "vds_min_V", "vds_max_V"]
    if "current_threshold_A" in result.columns:
        condition_columns.append("current_threshold_A")
    if "transfer_vds_V" in result.columns:
        condition_columns.append("transfer_vds_V")
    for condition, group in result.groupby(condition_columns, sort=False, dropna=False):
        baseline = group[group["stress_time_s"] == 0]
        if len(baseline) != 1:
            raise SchemaError(
                "each device/test-condition group must contain exactly one stress_time_s=0 baseline; "
                f"condition={condition!r} has {len(baseline)}"
            )
    result = result.sort_values(["device_id", "stress_time_s"]).reset_index(drop=True)
    baseline_values = result[result["stress_time_s"] == 0][condition_columns + ["vth_V", "ron_ohm"]].rename(
        columns={"vth_V": "vth_baseline_V", "ron_ohm": "ron_baseline_ohm"}
    )
    result = result.merge(baseline_values, on=condition_columns, how="left", validate="many_to_one")
    if result[["vth_baseline_V", "ron_baseline_ohm"]].isna().any().any():
        raise SchemaError("failed to map a unique baseline to every metrics row")
    result["delta_vth_V"] = result["vth_V"] - result["vth_baseline_V"]
    result["normalized_ron"] = result["ron_ohm"] / result["ron_baseline_ohm"]
    return result


@dataclass(frozen=True)
class WeibullFit:
    n_complete: int
    beta: float
    eta_s: float
    n_censored: int
    note: str = "full-failure two-parameter MLE; no censored rows accepted"


def _weibull_score(beta: float, log_times: np.ndarray, times: np.ndarray) -> float:
    weights = np.exp(beta * log_times - np.max(beta * log_times))
    weighted_log_mean = float(np.sum(weights * log_times) / np.sum(weights))
    return weighted_log_mean - float(np.mean(log_times)) - 1.0 / beta


def fit_weibull(
    failure_frame: pd.DataFrame,
    time_column: str = "failure_time_s",
    observed_column: str = "event_observed",
) -> WeibullFit:
    """Fit a strict full-failure two-parameter Weibull MLE.

    This intentionally rejects right-censored rows instead of silently dropping
    them.  A proper right-censored likelihood is outside this teaching project.
    """

    required = {time_column, observed_column}
    if not required.issubset(failure_frame.columns):
        raise SchemaError(f"failure CSV missing columns: {', '.join(sorted(required - set(failure_frame.columns)))}")
    work = failure_frame.copy()
    work[time_column] = pd.to_numeric(work[time_column], errors="coerce")
    work[observed_column] = pd.to_numeric(work[observed_column], errors="coerce")
    if work.empty or work[[time_column, observed_column]].isna().any().any():
        raise SchemaError("failure time and event_observed must be numeric")
    if not np.isfinite(work[[time_column, observed_column]].to_numpy(dtype=float)).all():
        raise SchemaError("failure time and event_observed must be finite")
    observed_values = work[observed_column].to_numpy(dtype=float)
    if not np.isin(observed_values, [0.0, 1.0]).all():
        raise SchemaError("event_observed must contain only 0 or 1")
    times = work[time_column].to_numpy(dtype=float)
    if (times <= 0).any():
        raise SchemaError("all failure_time_s values must be positive")
    censored = work[work[observed_column] == 0]
    if len(censored):
        raise AnalysisError(
            "censored rows are not silently excluded; provide a full-failure CSV or implement a right-censored likelihood"
        )
    complete = work[work[observed_column] == 1]
    if len(complete) < 2:
        raise AnalysisError("Weibull MLE requires at least two positive complete failures")
    times = complete[time_column].to_numpy(dtype=float)
    log_times = np.log(times)
    # The score is negative near beta -> 0 and positive for sufficiently large beta.
    low, high = 1e-4, 1.0
    while _weibull_score(high, log_times, times) <= 0 and high < 1e6:
        high *= 2.0
    if _weibull_score(high, log_times, times) <= 0:
        raise AnalysisError("could not bracket Weibull shape MLE")
    for _ in range(160):
        middle = (low + high) / 2.0
        if _weibull_score(middle, log_times, times) > 0:
            high = middle
        else:
            low = middle
    beta = (low + high) / 2.0
    eta = float(np.mean(times**beta) ** (1.0 / beta))
    return WeibullFit(
        n_complete=int(len(complete)),
        beta=float(beta),
        eta_s=eta,
        n_censored=0,
    )


def write_weibull_summary(fit: WeibullFit, path: str | Path) -> None:
    pd.DataFrame(
        [
            {
                "n_complete": fit.n_complete,
                "n_censored_rejected": fit.n_censored,
                "beta_shape": fit.beta,
                "eta_scale_s": fit.eta_s,
                "note": fit.note,
            }
        ]
    ).to_csv(path, index=False)


def _scale_points(xs: Sequence[float], ys: Sequence[float], width: int = 900, height: int = 520):
    x_values = np.asarray(xs, dtype=float)
    y_values = np.asarray(ys, dtype=float)
    x_min, x_max = float(np.min(x_values)), float(np.max(x_values))
    y_min, y_max = float(np.min(y_values)), float(np.max(y_values))
    if x_max == x_min:
        x_max = x_min + 1.0
    if y_max == y_min:
        y_max = y_min + 1.0
    margin_x, margin_y = 75.0, 55.0
    plot_w, plot_h = width - 2 * margin_x, height - 2 * margin_y
    px = margin_x + (x_values - x_min) / (x_max - x_min) * plot_w
    py = height - margin_y - (y_values - y_min) / (y_max - y_min) * plot_h
    return px, py, x_min, x_max, y_min, y_max, margin_x, margin_y


def _svg_document(title: str, body: str, width: int = 900, height: int = 520) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="white"/>'
        f'<text x="45" y="32" font-family="Arial" font-size="20" font-weight="bold">{html.escape(title)}</text>'
        f"{body}</svg>"
    )


def _axes(width: int, height: int, x_min: float, x_max: float, y_min: float, y_max: float, margin_x: float, margin_y: float, xlabel: str, ylabel: str) -> str:
    x0, y0 = margin_x, height - margin_y
    x1, y1 = width - margin_x, margin_y
    parts = [
        f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="#333"/>',
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#333"/>',
        f'<text x="{(x0+x1)/2:.1f}" y="{height-12}" text-anchor="middle" font-family="Arial" font-size="14">{html.escape(xlabel)}</text>',
        f'<text x="16" y="{(y0+y1)/2:.1f}" transform="rotate(-90 16 {(y0+y1)/2:.1f})" text-anchor="middle" font-family="Arial" font-size="14">{html.escape(ylabel)}</text>',
    ]
    # Four intervals give five labeled ticks without crowding the compact SVG.
    for fraction in np.linspace(0.0, 1.0, 5):
        x_value = x_min + fraction * (x_max - x_min)
        y_value = y_min + fraction * (y_max - y_min)
        x = x0 + fraction * (x1 - x0)
        y = y0 - fraction * (y0 - y1)
        parts.append(f'<line x1="{x:.2f}" y1="{y0:.2f}" x2="{x:.2f}" y2="{y1:.2f}" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<line x1="{x0:.2f}" y1="{y:.2f}" x2="{x1:.2f}" y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{x:.2f}" y="{y0+24:.2f}" text-anchor="middle" font-family="Arial" font-size="11">{x_value:.3g}</text>')
        parts.append(f'<text x="{x0-8:.2f}" y="{y+4:.2f}" text-anchor="end" font-family="Arial" font-size="11">{y_value:.3g}</text>')
    return "".join(parts)


def _legend(items: Sequence[tuple[str, str, str]], x: float = 620.0, y: float = 72.0, note: str | None = None) -> str:
    """Render a compact line legend separate from curve endpoints."""

    parts: list[str] = []
    for index, (label, color, dash) in enumerate(items):
        yy = y + index * 18.0
        parts.append(f'<line x1="{x:.1f}" y1="{yy:.1f}" x2="{x+24:.1f}" y2="{yy:.1f}" stroke="{color}" stroke-width="2" {dash}/>' )
        parts.append(f'<text x="{x+30:.1f}" y="{yy+4:.1f}" font-family="Arial" font-size="12">{html.escape(label)}</text>')
    if note:
        parts.append(f'<text x="{x:.1f}" y="{y + len(items)*18.0 + 4:.1f}" font-family="Arial" font-size="11" fill="#555">{html.escape(note)}</text>')
    return "".join(parts)


def write_transfer_plot(frame: pd.DataFrame, path: str | Path, current_threshold_a: float) -> None:
    transfer = frame[frame["sweep"] == "transfer"]
    if transfer.empty:
        return
    # Plot each device's complete baseline transfer sweep.  Taking ``head(1)``
    # would leave a one-point "curve" and obscure the extraction context.
    baseline_time = transfer.groupby(["device_id", "temperature_C"])["stress_time_s"].transform("min")
    representative = transfer[transfer["stress_time_s"] == baseline_time]
    x_all = transfer["Vg_V"].to_numpy(float)
    y_all = transfer["Id_A"].to_numpy(float)
    px, py, x0, x1, y0, y1, mx, my = _scale_points(x_all, y_all)
    body = _axes(900, 520, x0, x1, y0, y1, mx, my, "Vg (V)", "Id (A)")
    def map_global(gx: np.ndarray, gy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        plot_w, plot_h = 900 - 2 * mx, 520 - 2 * my
        sx = mx + (gx - x0) / (x1 - x0) * plot_w
        sy = 520 - my - (gy - y0) / (y1 - y0) * plot_h
        return sx, sy
    colors = ["#2563eb", "#dc2626", "#059669", "#7c3aed"]
    for index, (device, group) in enumerate(representative.groupby("device_id")):
        gx = group["Vg_V"].to_numpy(float)
        gy = group["Id_A"].to_numpy(float)
        sx, sy = map_global(gx, gy)
        points = " ".join(f"{a:.2f},{b:.2f}" for a, b in zip(sx, sy))
        color = colors[index % len(colors)]
        body += f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>'
    body += _legend([(str(device), colors[index % len(colors)], "") for index, device in enumerate(representative["device_id"].drop_duplicates())], note="synthetic baseline transfer")
    threshold_y = map_global(np.array([x0, x1]), np.array([current_threshold_a, current_threshold_a]))[1]
    body += f'<line x1="{mx}" y1="{threshold_y[0]:.2f}" x2="{900-mx}" y2="{threshold_y[1]:.2f}" stroke="#111" stroke-dasharray="6,4"/>'
    body += '<text x="85" y="75" font-family="Arial" font-size="12">dashed: Ith = %.3g A</text>' % current_threshold_a
    Path(path).write_text(_svg_document("Representative transfer curves (synthetic)", body), encoding="utf-8")


def write_stress_plot(metrics: pd.DataFrame, path: str | Path) -> None:
    if metrics.empty:
        return
    x = metrics["stress_time_s"].to_numpy(float)
    y = metrics["normalized_ron"].to_numpy(float)
    # Use a rank-like x coordinate so stress time zero remains visible.
    x_plot = np.log10(1.0 + x)
    px, py, x0, x1, y0, y1, mx, my = _scale_points(x_plot, y)
    body = _axes(900, 520, x0, x1, y0, y1, mx, my, "log10(1 + stress time / s)", "normalized RON")
    plot_w, plot_h = 900 - 2 * mx, 520 - 2 * my
    def map_global(gx: np.ndarray, gy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        sx = mx + (gx - x0) / (x1 - x0) * plot_w
        sy = 520 - my - (gy - y0) / (y1 - y0) * plot_h
        return sx, sy
    colors = ["#2563eb", "#dc2626", "#059669", "#7c3aed"]
    for index, (device, group) in enumerate(metrics.groupby("device_id")):
        gx = np.log10(1.0 + group["stress_time_s"].to_numpy(float))
        gy = group["normalized_ron"].to_numpy(float)
        sx, sy = map_global(gx, gy)
        points = " ".join(f"{a:.2f},{b:.2f}" for a, b in zip(sx, sy))
        color = colors[index % len(colors)]
        body += f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>'
        body += "".join(f'<circle cx="{a:.2f}" cy="{b:.2f}" r="3" fill="{color}"/>' for a, b in zip(sx, sy))
    body += _legend([(str(device), colors[index % len(colors)], "") for index, device in enumerate(metrics["device_id"].drop_duplicates())], note="overlap can reflect the shared synthetic stress law")
    Path(path).write_text(_svg_document("Stress response: normalized RON (synthetic)", body), encoding="utf-8")


def write_delta_vth_plot(metrics: pd.DataFrame, path: str | Path) -> None:
    """Write a global-scale stress plot for VTH shift, in volts."""

    if metrics.empty or "delta_vth_V" not in metrics.columns:
        raise SchemaError("metrics must contain delta_vth_V for the VTH shift plot")
    x_plot = np.log10(1.0 + metrics["stress_time_s"].to_numpy(float))
    y = metrics["delta_vth_V"].to_numpy(float)
    px, py, x0, x1, y0, y1, mx, my = _scale_points(x_plot, y)
    body = _axes(900, 520, x0, x1, y0, y1, mx, my, "log10(1 + stress time / s)", "ΔVTH (V)")
    plot_w, plot_h = 900 - 2 * mx, 520 - 2 * my
    def map_global(gx: np.ndarray, gy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        sx = mx + (gx - x0) / (x1 - x0) * plot_w
        sy = 520 - my - (gy - y0) / (y1 - y0) * plot_h
        return sx, sy
    colors = ["#2563eb", "#dc2626", "#059669", "#7c3aed"]
    for index, (device, group) in enumerate(metrics.groupby("device_id")):
        gx = np.log10(1.0 + group["stress_time_s"].to_numpy(float))
        gy = group["delta_vth_V"].to_numpy(float)
        sx, sy = map_global(gx, gy)
        points = " ".join(f"{a:.2f},{b:.2f}" for a, b in zip(sx, sy))
        color = colors[index % len(colors)]
        body += f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>'
        body += "".join(f'<circle cx="{a:.2f}" cy="{b:.2f}" r="3" fill="{color}"/>' for a, b in zip(sx, sy))
    body += _legend([(str(device), colors[index % len(colors)], "") for index, device in enumerate(metrics["device_id"].drop_duplicates())], note="ΔVTH is relative to each unique t=0 baseline")
    Path(path).write_text(_svg_document("Stress response: ΔVTH (synthetic)", body), encoding="utf-8")


def write_weibull_plot(failure_frame: pd.DataFrame, path: str | Path) -> None:
    # Validate through the same strict full-failure rules as the CSV summary;
    # this plot must not quietly omit censored or invalid rows.
    fit = fit_weibull(failure_frame)
    observed = failure_frame.copy().sort_values("failure_time_s")
    times = observed["failure_time_s"].to_numpy(float)
    ranks = (np.arange(1, len(times) + 1) - 0.3) / (len(times) + 0.4)
    x = np.log(times)
    y = np.log(-np.log(1.0 - ranks))
    px, py, x0, x1, y0, y1, mx, my = _scale_points(x, y)
    body = _axes(900, 520, x0, x1, y0, y1, mx, my, "ln(failure time / s)", "ln(-ln(1 - F))")
    body += "".join(f'<circle cx="{a:.2f}" cy="{b:.2f}" r="4" fill="#dc2626"/>' for a, b in zip(px, py))
    fit_x = np.array([x0, x1], dtype=float)
    fit_y = fit.beta * (fit_x - math.log(fit.eta_s))
    # Clip the displayed MLE segment to the observed probability-plot bounds;
    # the line is a visual fit to complete failures, not a lifetime forecast.
    if fit.beta > 0:
        lower_x = max(x0, math.log(fit.eta_s) + y0 / fit.beta)
        upper_x = min(x1, math.log(fit.eta_s) + y1 / fit.beta)
        fit_x = np.clip(fit_x, lower_x, upper_x)
        fit_y = fit.beta * (fit_x - math.log(fit.eta_s))
    # Map the fitted line to the data axes rather than rescaling it separately.
    plot_w, plot_h = 900 - 2 * mx, 520 - 2 * my
    fit_px = mx + (fit_x - x0) / (x1 - x0) * plot_w
    fit_py = 520 - my - (fit_y - y0) / (y1 - y0) * plot_h
    body += f'<polyline points="{fit_px[0]:.2f},{fit_py[0]:.2f} {fit_px[1]:.2f},{fit_py[1]:.2f}" fill="none" stroke="#2563eb" stroke-width="2" stroke-dasharray="7,4"/>'
    body += _legend(
        [("complete failure observations", "#dc2626", ""), (f"Weibull MLE β={fit.beta:.3g}, η={fit.eta_s:.3g} s", "#2563eb", 'stroke-dasharray="7,4"')],
        note="full failures only; fitted line is not an extrapolation",
    )
    Path(path).write_text(_svg_document("Weibull probability plot (complete synthetic failures)", body), encoding="utf-8")

