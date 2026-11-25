#!/usr/bin/env python3
"""Validate reproducibility artifacts before sharing the repository."""

from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "alerts_ref": ROOT / "results/2023/out_of_sample/wavelet_alerts_2023_Reference_T6.csv",
    "alerts_mit": ROOT / "results/2023/out_of_sample/wavelet_alerts_2023_Mitigation_T12.csv",
    "cat22": ROOT / "data/reference/2022/NOAA_CMX_reference_2022.csv",
    "cat23": ROOT / "data/reference/2023/sci_xrsf-l2-flrpt_geo_y2023_v1-0-1.csv",
    "cov22": ROOT / "data/coverage/GOES_2022_full_year_coverage_summary.csv",
    "cov23": ROOT / "data/coverage/GOES_2023_coverage_summary.csv",
}


def ensure_clean_text(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    first = path.open("r", encoding="utf-8", errors="replace").readline()
    if first.startswith("<PARSED TEXT FOR SHEET"):
        raise RuntimeError(f"Corrupt spreadsheet-preview text detected: {path}")


def scored_count(df, time_col, year):
    t = pd.to_datetime(df[time_col], utc=True)
    total = 0
    for m in range(1, 13):
        start = pd.Timestamp(f"{year}-{m:02d}-01", tz="UTC")
        end = start + pd.offsets.MonthBegin(1)
        total += int(((t >= start + pd.Timedelta(minutes=120)) & (t < end)).sum())
    return total


def main():
    for path in FILES.values():
        ensure_clean_text(path)

    ref = pd.read_csv(FILES["alerts_ref"])
    mit = pd.read_csv(FILES["alerts_mit"])
    cat22 = pd.read_csv(FILES["cat22"])
    cat23 = pd.read_csv(FILES["cat23"])
    cov22 = pd.read_csv(FILES["cov22"])
    cov23 = pd.read_csv(FILES["cov23"])

    assert len(ref) == 4430
    assert int((ref["stream"] == "prediction").sum()) == 3092
    assert int((ref["stream"] == "detection").sum()) == 1338

    assert len(mit) == 3998
    assert int((mit["stream"] == "prediction").sum()) == 2896
    assert int((mit["stream"] == "detection").sum()) == 1102

    assert len(cat22) == 2308
    assert scored_count(cat22, "peak_time", 2022) == 2305

    cmx23 = cat23.loc[
        cat23["flare_class"].astype(str).str[0].isin(["C", "M", "X"])
    ].copy()
    assert len(cmx23) == 3284
    assert scored_count(cmx23, "time", 2023) == 3268

    assert len(cov22) == 12
    assert len(cov23) == 1

    print("All reproducibility artifacts are clean and counts match the paper.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        raise
