#!/usr/bin/env python3
"""Download official GOES-16 XRS science inputs and prepare the 2022 archive.

The original 2022 analysis consumed a local flattened CSV ZIP named
GOES_2022_FULL.zip. The analysis code reads only:
    time, quad_diode, xrsb_flux, xrsb_flag
and then retains quad_diode == 0.

This utility downloads NOAA/NCEI's official GOES-16 Level-2 1-minute science
NetCDF files (v2-2-1) and creates an analysis-equivalent compact 2022 ZIP with
one quad_diode=0 row per minute. It also downloads the 2023 NetCDF used by
run_2023_alerts.py.
"""

from pathlib import Path
import argparse
import urllib.request

import h5py
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_2022 = REPO_ROOT / "data" / "raw" / "2022"
RAW_2023 = REPO_ROOT / "data" / "raw" / "2023"

BASE = (
    "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/"
    "goes/goes16/l2/data/xrsf-l2-avg1m_science"
)
URL_2022 = BASE + "/sci_xrsf-l2-avg1m_g16_y2022_v2-2-1.nc"
URL_2023 = BASE + "/sci_xrsf-l2-avg1m_g16_y2023_v2-2-1.nc"


def download(url: str, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print(f"Already present: {target}")
        return
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, target)
    print(f"Saved: {target}")


def read_time_and_xrs(path: Path) -> pd.DataFrame:
    with h5py.File(path, "r") as f:
        seconds = np.asarray(f["time"][:], dtype=float)
        flux = np.asarray(f["xrsb_flux"][:], dtype=float)
        flag = np.asarray(f["xrsb_flag"][:])

        fill = f["xrsb_flux"].attrs.get("_FillValue")
        if fill is not None:
            fill_value = float(np.asarray(fill).ravel()[0])
            flux[flux == fill_value] = np.nan

        units = f["time"].attrs.get(
            "units",
            b"seconds since 2000-01-01 12:00:00 UTC",
        )
        if isinstance(units, bytes):
            units = units.decode("utf-8")
        epoch_text = units.split("seconds since ", 1)[1].replace(" UTC", "Z")
        epoch = pd.Timestamp(epoch_text)

    time = epoch + pd.to_timedelta(seconds, unit="s")
    return pd.DataFrame({
        "time": time.tz_convert(None),
        "quad_diode": np.zeros(len(time), dtype=np.int8),
        "xrsb_flux": flux,
        "xrsb_flag": flag,
    })


def build_2022_zip(netcdf: Path, target_zip: Path):
    target_zip.parent.mkdir(parents=True, exist_ok=True)
    frame = read_time_and_xrs(netcdf)
    frame.to_csv(
        target_zip,
        index=False,
        compression={
            "method": "zip",
            "archive_name": "GOES_2022_FULL.csv",
        },
    )
    print(f"Built analysis-equivalent input: {target_zip}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--skip-2023",
        action="store_true",
        help="Download/prepare only the 2022 input.",
    )
    args = ap.parse_args()

    nc2022 = RAW_2022 / "sci_xrsf-l2-avg1m_g16_y2022_v2-2-1.nc"
    zip2022 = RAW_2022 / "GOES_2022_FULL.zip"
    nc2023 = RAW_2023 / "sci_xrsf-l2-avg1m_g16_y2023_v2-2-1.nc"

    download(URL_2022, nc2022)
    build_2022_zip(nc2022, zip2022)

    if not args.skip_2023:
        download(URL_2023, nc2023)


if __name__ == "__main__":
    main()
