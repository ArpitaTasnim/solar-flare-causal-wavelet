#!/usr/bin/env python3
"""Recompute the 2023 out-of-sample metrics from saved alert-event files.

This script verifies the reported 2023 TP/FP/FN, precision, recall, F1 and
timing metrics using the frozen wavelet alert events plus the NOAA 2023 flare
report. Alert files can be regenerated from the raw GOES-16 NetCDF with
run_2023_alerts.py, which reuses the causal core in run_2022_full_analysis.py.
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]\n\nWARMUP_MIN = 120
PRED_MIN_LEAD = 10
PRED_MAX_LEAD = 90
DET_TOL = 10


def load_refs(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["peak_time"] = pd.to_datetime(df["time"], utc=True)
    df["class"] = df["flare_class"].astype(str)
    df["class_letter"] = df["class"].str[0]
    df["event_id"] = df["flare_id"].astype(str)
    return df.loc[df["class_letter"].isin(["C", "M", "X"])].copy()


def month_refs(refs: pd.DataFrame, month: str) -> pd.DataFrame:
    start = pd.Timestamp(month + "-01", tz="UTC")
    end = start + pd.offsets.MonthBegin(1)
    return refs.loc[
        (refs["peak_time"] >= start + pd.Timedelta(minutes=WARMUP_MIN))
        & (refs["peak_time"] < end)
    ].sort_values(["peak_time", "event_id"]).reset_index(drop=True)


def greedy_match(alerts: pd.DataFrame, refs: pd.DataFrame, stream: str):
    alerts = alerts.sort_values(["start_time", "alert_id"]).copy()
    peaks = refs["peak_time"].astype("int64").to_numpy()
    available = np.ones(len(refs), dtype=bool)
    rows = []
    for a in alerts.itertuples(index=False):
        t_ns = pd.Timestamp(a.start_time).value
        if stream == "prediction":
            lo = t_ns + PRED_MIN_LEAD * 60 * 1_000_000_000
            hi = t_ns + PRED_MAX_LEAD * 60 * 1_000_000_000
        else:
            lo = t_ns - DET_TOL * 60 * 1_000_000_000
            hi = t_ns + DET_TOL * 60 * 1_000_000_000
        left = int(np.searchsorted(peaks, lo, side="left"))
        right = int(np.searchsorted(peaks, hi, side="right"))
        cand = np.flatnonzero(available[left:right]) + left
        if cand.size == 0:
            continue
        if stream == "prediction":
            i = int(cand[0])
        else:
            i = int(cand[np.argmin(np.abs(peaks[cand] - t_ns))])
        available[i] = False
        r = refs.iloc[i]
        t = pd.Timestamp(a.start_time)
        lead = (r["peak_time"] - t).total_seconds() / 60.0
        rows.append({
            "month": a.month, "stream": stream, "alert_id": a.alert_id,
            "alert_start_time": t, "event_id": r["event_id"],
            "noaa_peak_time": r["peak_time"], "noaa_class": r["class"],
            "lead_minutes": lead, "offset_minutes": -lead,
        })
    return pd.DataFrame(rows)


def evaluate(alert_file: Path, refs: pd.DataFrame, setting: str):
    alerts = pd.read_csv(alert_file)
    alerts["start_time"] = pd.to_datetime(alerts["start_time"], utc=True)
    if "month" not in alerts.columns:
        alerts["month"] = alerts["start_time"].dt.strftime("%Y-%m")

    monthly_rows, all_matches = [], []
    for month in [f"2023-{m:02d}" for m in range(1, 13)]:
        r = month_refs(refs, month)
        for stream in ["prediction", "detection"]:
            a = alerts.loc[(alerts["month"] == month) & (alerts["stream"] == stream)].copy()
            matched = greedy_match(a, r, stream)
            if not matched.empty:
                all_matches.append(matched)
            tp = len(matched); fp = len(a) - tp; fn = len(r) - tp
            precision = tp / len(a) if len(a) else 0.0
            recall = tp / len(r) if len(r) else np.nan
            f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else np.nan
            timing = (float(np.median(matched["lead_minutes"])) if tp and stream == "prediction"
                      else float(np.median(np.abs(matched["offset_minutes"]))) if tp else np.nan)
            monthly_rows.append({
                "setting": setting, "month": month, "stream": stream,
                "alerts_issued": len(a), "noaa_cmx_events": len(r),
                "TP": tp, "FP": fp, "FN": fn,
                "precision": precision, "recall": recall, "F1": f1,
                "timing": timing,
            })

    monthly = pd.DataFrame(monthly_rows)
    matches = pd.concat(all_matches, ignore_index=True) if all_matches else pd.DataFrame()
    pooled_rows = []
    for stream in ["prediction", "detection"]:
        d = monthly.loc[monthly["stream"] == stream]
        tp, fp, fn = int(d.TP.sum()), int(d.FP.sum()), int(d.FN.sum())
        alerts_n = int(d.alerts_issued.sum()); refs_n = int(d.noaa_cmx_events.sum())
        precision = tp / alerts_n; recall = tp / refs_n
        f1 = 2 * tp / (2 * tp + fp + fn)
        mm = matches.loc[matches["stream"] == stream]
        timing = (float(np.median(mm["lead_minutes"])) if stream == "prediction"
                  else float(np.median(np.abs(mm["offset_minutes"]))))
        pooled_rows.append({
            "setting": setting, "stream": stream,
            "alerts_issued": alerts_n, "noaa_cmx_events": refs_n,
            "TP": tp, "FP": fp, "FN": fn,
            "precision": precision, "recall": recall, "F1": f1,
            "timing": timing,
            "false_alarm_fraction": fp / alerts_n,
            "miss_fraction": fn / refs_n,
        })
    return monthly, pd.DataFrame(pooled_rows), matches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, default=REPO_ROOT / "data" / "reference" / "2023" / "sci_xrsf-l2-flrpt_geo_y2023_v1-0-1.csv")
    ap.add_argument("--alerts-dir", type=Path, default=REPO_ROOT / "results" / "2023" / "out_of_sample")
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "results" / "2023" / "recomputed_verification")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    refs = load_refs(args.catalog)
    specs = [
        ("Reference_T6", args.alerts_dir / "wavelet_alerts_2023_Reference_T6.csv"),
        ("Mitigation_T12", args.alerts_dir / "wavelet_alerts_2023_Mitigation_T12.csv"),
    ]
    pooled_all = []
    for setting, path in specs:
        monthly, pooled, matches = evaluate(path, refs, setting)
        monthly.to_csv(args.out_dir / f"monthly_metrics_2023_{setting}.csv", index=False)
        pooled.to_csv(args.out_dir / f"pooled_metrics_2023_{setting}.csv", index=False)
        matches.to_csv(args.out_dir / f"matches_2023_{setting}.csv", index=False)
        pooled_all.append(pooled)
    combined = pd.concat(pooled_all, ignore_index=True)
    combined.to_csv(args.out_dir / "pooled_metrics_2023_all_settings.csv", index=False)
    print(combined.to_string(index=False))


if __name__ == "__main__":
    main()
