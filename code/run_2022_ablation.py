#!/usr/bin/env python3
"""Re-run the 2022 one-factor-at-a-time wavelet sensitivity analysis."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse

import numpy as np
import pandas as pd

import run_2022_full_analysis as core


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOES = REPO_ROOT / "data" / "raw" / "2022" / "GOES_2022_FULL.zip"
DEFAULT_REFS = REPO_ROOT / "data" / "reference" / "2022" / "NOAA_CMX_reference_2022.csv"
DEFAULT_OUT = REPO_ROOT / "results" / "2022" / "generated_ablation"


def load_refs(path: Path) -> pd.DataFrame:
    refs = pd.read_csv(path)
    refs["peak_time"] = pd.to_datetime(refs["peak_time"], utc=True)
    if "event_id" not in refs:
        refs["event_id"] = np.arange(len(refs)).astype(str)
    return refs


def evaluate_cfg(goes, refs, cfg):
    months = [f"2022-{m:02d}" for m in range(1, 13)]
    monthly = []
    matches = {"prediction": [], "detection": []}

    for month in months:
        part = core.regularize(goes, month)
        start = pd.Timestamp(month + "-01", tz="UTC")
        end = start + pd.offsets.MonthBegin(1)

        r = refs.loc[
            (refs["peak_time"] >= start + pd.Timedelta(minutes=cfg.warmup_minutes))
            & (refs["peak_time"] < end)
            & (refs["class_letter"].isin(["C", "M", "X"]))
        ].copy()

        decisions = core.compute_wavelet_decisions(part, cfg)

        for stream in ("prediction", "detection"):
            alerts = core.eventize_wavelet(
                decisions, stream, cfg, month_end=end
            )
            metric, matched = core.match_wavelet(
                alerts, r, stream, cfg
            )
            monthly.append({"month": month, "stream": stream, **metric})
            if not matched.empty:
                matches[stream].append(matched)

    monthly = pd.DataFrame(monthly)
    out = {}

    for stream in ("prediction", "detection"):
        d = monthly.loc[monthly["stream"] == stream]
        tp = int(d["TP"].sum())
        fp = int(d["FP"].sum())
        fn = int(d["FN"].sum())
        precision = tp / (tp + fp) if tp + fp else np.nan
        recall = tp / (tp + fn) if tp + fn else np.nan
        f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else np.nan

        mm = (
            pd.concat(matches[stream], ignore_index=True)
            if matches[stream]
            else pd.DataFrame()
        )

        rec = {
            "precision": precision,
            "recall": recall,
            "F1": f1,
        }
        if stream == "prediction":
            rec["median_lead_min"] = (
                float(np.median(mm["lead_minutes"])) if len(mm) else np.nan
            )
        else:
            rec["median_abs_offset_min"] = (
                float(np.median(np.abs(mm["offset_minutes"])))
                if len(mm) else np.nan
            )
        out[stream] = rec

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goes-zip", type=Path, default=DEFAULT_GOES)
    ap.add_argument("--reference", type=Path, default=DEFAULT_REFS)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    goes = core.read_goes_full_year(args.goes_zip)
    refs = load_refs(args.reference)

    variants = [
        ("Wavelet", "db1", replace(core.CFG, wavelet="db1")),
        ("Wavelet", "db2", replace(core.CFG, wavelet="db2")),
        ("Wavelet", "db4", replace(core.CFG, wavelet="db4")),
        ("Window K", "24 min", replace(core.CFG, window_minutes=24)),
        ("Window K", "30 min", replace(core.CFG, window_minutes=30)),
        ("Window K", "45 min", replace(core.CFG, window_minutes=45)),
        ("Qpred", "0.75", replace(core.CFG, prediction_quantile=0.75)),
        ("Qpred", "0.80", replace(core.CFG, prediction_quantile=0.80)),
        ("Qpred", "0.85", replace(core.CFG, prediction_quantile=0.85)),
        ("Qdet", "0.90", replace(core.CFG, detection_quantile=0.90)),
        ("Qdet", "0.95", replace(core.CFG, detection_quantile=0.95)),
        ("Qdet", "0.97", replace(core.CFG, detection_quantile=0.97)),
        ("History T", "3 h", replace(core.CFG, horizon_minutes=180)),
        ("History T", "6 h", replace(core.CFG, horizon_minutes=360)),
        ("History T", "12 h", replace(core.CFG, horizon_minutes=720)),
    ]

    pred_rows = []
    det_rows = []
    cache = {}

    for group, label, cfg in variants:
        key = (
            cfg.wavelet, cfg.window_minutes, cfg.horizon_minutes,
            cfg.prediction_quantile, cfg.detection_quantile
        )
        if key not in cache:
            print(f"Running {group}: {label}")
            cache[key] = evaluate_cfg(goes, refs, cfg)
        res = cache[key]

        if group != "Qdet":
            pred_rows.append({
                "group": group,
                "variant": label,
                **res["prediction"],
            })
        if group != "Qpred":
            det_rows.append({
                "group": group,
                "variant": label,
                **res["detection"],
            })

    pred = pd.DataFrame(pred_rows)
    det = pd.DataFrame(det_rows)

    ref_pred = pred.loc[
        (pred["group"] == "Wavelet") & (pred["variant"] == "db2"), "F1"
    ].iloc[0]
    ref_det = det.loc[
        (det["group"] == "Wavelet") & (det["variant"] == "db2"), "F1"
    ].iloc[0]

    pred["delta_F1_vs_reference"] = pred["F1"] - ref_pred
    det["delta_F1_vs_reference"] = det["F1"] - ref_det

    pred.to_csv(
        args.out_dir / "Prediction_ablation_full_year_2022.csv",
        index=False,
    )
    det.to_csv(
        args.out_dir / "Detection_ablation_full_year_2022.csv",
        index=False,
    )

    print(pred.to_string(index=False))
    print(det.to_string(index=False))


if __name__ == "__main__":
    main()
