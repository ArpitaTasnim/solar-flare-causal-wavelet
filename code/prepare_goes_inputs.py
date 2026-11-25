#!/usr/bin/env python3
"""Download official NOAA/NCEI GOES inputs used by this repository."""

from pathlib import Path
import argparse
import hashlib
import urllib.request

import h5py
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_2022 = REPO_ROOT / "data" / "raw" / "2022"
RAW_2023 = REPO_ROOT / "data" / "raw" / "2023"
REF_2023 = REPO_ROOT / "data" / "reference" / "2023"
COVERAGE = REPO_ROOT / "data" / "coverage"

AVG1M_BASE = (
    "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/"
    "goes/goes16/l2/data/xrsf-l2-avg1m_science"
)
FLRPT_BASE = (
    "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/"
    "goes/multi/l2/data/xrsf-l2-flrpt_science/csv"
)

URL_2022 = "https://github.com/ArpitaTasnim/solar-flare-causal-wavelet/releases/download/data-v1.0/GOES_2022_FULL.zip"
SHA256_2022 = "67b63eae17245227ccc51b77612c496384b76fda4954eede9c89abb1bf62242e"
URL_2023 = "https://github.com/ArpitaTasnim/solar-flare-causal-wavelet/releases/download/data-v1.0/sci_xrsf-l2-avg1m_g16_y2023_v2-2-1.nc"
SHA256_2023 = "c25cde23fe3ecb1b6185ec823126cd0d68893461216d3f2ca687e1c08034af31"
URL_2023_FLRPT = "https://github.com/ArpitaTasnim/solar-flare-causal-wavelet/releases/download/data-v1.0/sci_xrsf-l2-flrpt_geo_y2023_v1-0-1.csv"
SHA256_2023_FLRPT = "23902fe462a5eafc500ea15d897d59e57480526d83dda448b9047ead4a89dbe5"


def download(url: str, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        print(f"Already present: {target}")
        return
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, target)
    print(f"Saved: {target}")


def read_netcdf(path: Path):
    with h5py.File(path, "r") as f:
        seconds = np.asarray(f["time"][:], dtype=float)
        flux = np.asarray(f["xrsb_flux"][:], dtype=float)
        flag = np.asarray(f["xrsb_flag"][:])

        fill = f["xrsb_flux"].attrs.get("_FillValue")
        if fill is not None:
            fill_value = float(np.asarray(fill).ravel()[0])
            flux[flux == fill_value] = np.nan

        units = f["time"].attrs.get(
            "units", b"seconds since 2000-01-01 12:00:00 UTC"
        )
        if isinstance(units, bytes):
            units = units.decode("utf-8")
        epoch_text = units.split("seconds since ", 1)[1].replace(" UTC", "Z")
        epoch = pd.Timestamp(epoch_text)

    time = epoch + pd.to_timedelta(seconds, unit="s")
    return pd.DatetimeIndex(time), flux, flag


def build_2022_zip(netcdf: Path, target_zip: Path):
    time, flux, flag = read_netcdf(netcdf)
    frame = pd.DataFrame({
        "time": time.tz_convert(None),
        "quad_diode": np.zeros(len(time), dtype=np.int8),
        "xrsb_flux": flux,
        "xrsb_flag": flag,
    })
    target_zip.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(
        target_zip,
        index=False,
        compression={"method": "zip", "archive_name": "GOES_2022_FULL.csv"},
    )
    print(f"Built analysis input: {target_zip}")


def write_2022_coverage(archive: Path):
    from run_2022_full_analysis import read_goes_full_year
    frame = read_goes_full_year(archive)
    df = frame.reset_index().rename(columns={"xrsb_flux": "flux", "xrsb_flag": "flag"})
    if "time" not in df:
        df = df.rename(columns={df.columns[0]: "time"})
    rows = []
    for m in range(1, 13):
        month = f"2022-{m:02d}"
        start = pd.Timestamp(month + "-01", tz="UTC")
        end = start + pd.offsets.MonthBegin(1)
        d = df.loc[(df["time"] >= start) & (df["time"] < end)]
        expected = len(pd.date_range(start, end, freq="min", inclusive="left"))
        rows.append({
            "month": month,
            "minutes": len(d),
            "expected_minutes": expected,
            "missing_xrsb_flux_minutes": int((~np.isfinite(d["flux"])).sum()),
            "nonzero_xrsb_flag_minutes": int((d["flag"] != 0).sum()),
            "flux_available_fraction": float(np.isfinite(d["flux"]).mean()),
            "first_time": d["time"].min(),
            "last_time": d["time"].max(),
        })
    COVERAGE.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(
        COVERAGE / "GOES_2022_full_year_coverage_summary.csv", index=False
    )


def write_2023_coverage(netcdf: Path):
    time, flux, _ = read_netcdf(netcdf)
    valid = np.isfinite(flux)
    row = pd.DataFrame([{
        "rows": len(flux),
        "start": time.min(),
        "end": time.max(),
        "finite_flux": int(valid.sum()),
        "negative_flux": int((valid & (flux < 0)).sum()),
        "median_flux": float(np.nanmedian(flux)),
    }])
    COVERAGE.mkdir(parents=True, exist_ok=True)
    row.to_csv(COVERAGE / "GOES_2023_coverage_summary.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--only-2023", action="store_true",
        help="Prepare only the 2023 NetCDF, flare report, and coverage summary."
    )
    args = ap.parse_args()

    nc2023 = RAW_2023 / "sci_xrsf-l2-avg1m_g16_y2023_v2-2-1.nc"
    flare2023 = REF_2023 / "sci_xrsf-l2-flrpt_geo_y2023_v1-0-1.csv"

    if not args.only_2023:
        zip2022 = RAW_2022 / "GOES_2022_FULL.zip"
        download(URL_2022, zip2022)
        with zip2022.open("rb") as f:
            actual = hashlib.file_digest(f, "sha256").hexdigest()
        if actual != SHA256_2022:
            raise ValueError(f"Original 2022 archive checksum mismatch: {actual}")
        write_2022_coverage(zip2022)

    download(URL_2023, nc2023)
    download(URL_2023_FLRPT, flare2023)
    for path, expected in [(nc2023, SHA256_2023), (flare2023, SHA256_2023_FLRPT)]:
        with path.open("rb") as f:
            actual = hashlib.file_digest(f, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"Original 2023 input checksum mismatch: {path}: {actual}")
    write_2023_coverage(nc2023)


if __name__ == "__main__":
    main()
