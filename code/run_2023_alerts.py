#!/usr/bin/env python3
"""Generate the 2023 frozen wavelet alert files from GOES-16 XRS NetCDF.

This script reads the GOES-16 science-quality 1-minute XRS product and reuses
the exact causal wavelet/eventization functions from run_2022_full_analysis.py.
No 2023 labels are used while generating alerts.

Reference setting: T = 6 h.
Mitigation setting: T = 12 h.
All other parameters remain fixed.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse

import h5py
import numpy as np
import pandas as pd

import run_2022_full_analysis as core


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NETCDF = (
    REPO_ROOT / "data" / "raw" / "2023"
    / "sci_xrsf-l2-avg1m_g16_y2023_v2-2-1.nc"
)
DEFAULT_OUTPUT = REPO_ROOT / "results" / "2023" / "out_of_sample"


def load_goes_xrs(path: Path) -> pd.DataFrame:
    """Load xrsb_flux and convert NetCDF time coordinates to UTC timestamps."""
    with h5py.File(path, "r") as f:
        t = np.asarray(f["time"][:], dtype=float)
        flux = np.asarray(f["xrsb_flux"][:], dtype=float)

        fill = f["xrsb_flux"].attrs.get("_FillValue")
        if fill is not None:
            fill_value = float(np.asarray(fill).ravel()[0])
            flux[flux == fill_value] = np.nan

        units = f["time"].attrs.get("units", b"seconds since 2000-01-01 12:00:00 UTC")
        if isinstance(units, bytes):
            units = units.decode("utf-8")
        if "seconds since " not in units:
            raise ValueError(f"Unsupported time units: {units}")
        epoch_text = units.split("seconds since ", 1)[1].replace(" UTC", "Z")
        epoch = pd.Timestamp(epoch_text)

    index = epoch + pd.to_timedelta(t, unit="s")
    frame = pd.DataFrame({"xrsb_flux": flux}, index=pd.DatetimeIndex(index))
    frame = frame.sort_index().loc["2023-01-01":"2023-12-31 23:59:59"]
    return frame


def generate_setting(
    goes: pd.DataFrame,
    setting: str,
    horizon_minutes: int,
) -> pd.DataFrame:
    cfg = replace(core.CFG, horizon_minutes=horizon_minutes)
    rows = []

    for m in range(1, 13):
        month = f"2023-{m:02d}"
        start = pd.Timestamp(month + "-01", tz="UTC")
        end = start + pd.offsets.MonthBegin(1)

        grid = pd.date_range(start, end, freq="min", inclusive="left")
        part = goes.loc[(goes.index >= start) & (goes.index < end)].reindex(grid)

        decisions = core.compute_wavelet_decisions(part, cfg)

        for stream in ("prediction", "detection"):
            alerts = core.eventize_wavelet(
                decisions,
                stream,
                cfg,
                month_end=end,
            )
            if alerts.empty:
                continue
            alerts.insert(0, "month", month)
            alerts.insert(0, "setting", setting)
            rows.append(alerts)

    if not rows:
        return pd.DataFrame(columns=["setting", "month", *core.ALERT_COLUMNS])

    return pd.concat(rows, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--netcdf", type=Path, default=DEFAULT_NETCDF)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    if not args.netcdf.exists():
        raise FileNotFoundError(
            f"Missing GOES input: {args.netcdf}\n"
            "See docs/DATA_SOURCES.md for the NOAA/NCEI download source."
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    goes = load_goes_xrs(args.netcdf)

    specs = [
        ("Reference_T6", 360),
        ("Mitigation_T12", 720),
    ]

    for setting, horizon in specs:
        alerts = generate_setting(goes, setting, horizon)
        out = args.out_dir / f"wavelet_alerts_2023_{setting}.csv"
        alerts.to_csv(out, index=False)

        counts = alerts.groupby("stream").size().to_dict()
        print(f"{setting}: {counts} -> {out}")


if __name__ == "__main__":
    main()
