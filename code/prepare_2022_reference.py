#!/usr/bin/env python3
"""Download and parse the 2022 NOAA/SWPC C/M/X flare reference catalog."""

from pathlib import Path
import argparse

import run_2022_full_analysis as core


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPO_ROOT / "data" / "reference" / "2022" / "NOAA_CMX_reference_2022.csv"
)
DEFAULT_CACHE = REPO_ROOT / "data" / "raw" / "2022" / "NOAA_daily_event_reports"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    args = ap.parse_args()

    catalog = core.fetch_noaa_reports(args.cache_dir)
    cmx = catalog.loc[catalog["class_letter"].isin(["C", "M", "X"])].copy()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cmx.to_csv(
        args.output,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )
    print(f"Saved {len(cmx):,} C/M/X events to {args.output}")


if __name__ == "__main__":
    main()
