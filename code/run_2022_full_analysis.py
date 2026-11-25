# -*- coding: utf-8 -*-
"""
FULL-YEAR 2022 SOLAR-FLARE EVALUATION

What this script does
---------------------
1. Finds GOES_2022_FULL.zip (or uses GOES_ZIP below).
2. Downloads the 365 NOAA/SWPC daily Solar Event Reports for 2022.
3. Parses XRA events and keeps C/M/X events as the independent reference.
4. Runs the fixed causal wavelet method month-by-month for Jan-Dec 2022:
      db2, level 3, K=30 min, decision=2 min, T=6 h,
      warm-up=120 min, Qpred=0.80, Qdet=0.95,
      persistence=4 min, merge gap=12 min.
5. Runs four causal forecasting baselines:
      SMA (105 min, ×1.31; 10–90 min)
      SMA (10 min, ×1.10; 10–90 min)
      EWMA (10 min, ×1.05; 10–90 min)
      Slope (20 min, log-flux; 10–90 min)
6. Saves monthly and pooled full-year results, plus an 11-month
   non-April summary because April was used to select/calibrate the
   added baseline operating points.

Dependencies
------------
pip install numpy pandas matplotlib pywavelets requests

Notes
-----
- NOAA/SWPC event reports are the independent labels; do not derive
  labels from GOES flux itself.
- Every month is initialized independently, matching the April-July
  extension pipeline.
- All alert features/thresholds are causal; no future flux is used.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import calendar
import hashlib
import re
import time
import zipfile

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pywt

try:
    import requests
except Exception:
    requests = None


# ============================================================
# USER SETTINGS
# ============================================================

GOES_ZIP = None
# Example:
# GOES_ZIP = r"C:\Users\HP\Downloads\GOES_2022_FULL.zip"

OUTPUT_FOLDER = str(Path.home() / "Downloads" / "SolarFlare_2022_FullYear")

YEAR = 2022

# Fixed slope threshold selected on April in the earlier baseline analysis.
SLOPE_THRESHOLD_DEX_PER_MIN = 0.0035452873815516642


# ============================================================
# CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class Config:
    wavelet: str = "db2"
    level: int = 3
    extension_mode: str = "symmetric"
    window_minutes: int = 30
    decision_minutes: int = 2
    horizon_minutes: int = 360
    warmup_minutes: int = 120
    prediction_quantile: float = 0.80
    detection_quantile: float = 0.95
    quantile_method: str = "linear"
    persistence_minutes: int = 4
    merge_gap_minutes: int = 12
    interpolate_max_missing_minutes: int = 2
    prediction_min_lead_minutes: int = 10
    prediction_max_lead_minutes: int = 90
    detection_tolerance_minutes: int = 10


CFG = Config()

ALERT_COLUMNS = [
    "alert_id", "stream", "start_time", "crossing_start_time", "end_time",
    "priority", "energy_at_start", "threshold_at_start", "flux_at_start",
    "raw_alerts_merged", "segment_id", "right_censored",
]

MATCH_COLUMNS = [
    "alert_id", "stream", "alert_start_time", "crossing_start_time",
    "event_id", "noaa_peak_time", "noaa_class", "lead_minutes",
    "offset_minutes", "priority", "timing_basis",
]


# ============================================================
# PATHS
# ============================================================

def locate_goes_zip() -> Path:
    if GOES_ZIP:
        p = Path(GOES_ZIP).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"GOES_ZIP not found: {p}")
        return p

    candidates = []
    for folder in [Path.cwd(), Path.home() / "Downloads", Path.home() / "Download"]:
        if folder.exists():
            candidates.extend(folder.glob("GOES_2022_FULL*.zip"))

    candidates = sorted(
        set(candidates),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not candidates:
        raise FileNotFoundError(
            "Could not find GOES_2022_FULL.zip automatically. "
            "Set GOES_ZIP at the top of this script."
        )

    print("Auto-found GOES ZIP:", candidates[0])
    return candidates[0]


# ============================================================
# NOAA DOWNLOAD AND PARSING
# ============================================================

NCEI_BASE = (
    "https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/"
    "daily_reports/solar_event_reports"
)
CDAW_BASE = "https://cdaw.gsfc.nasa.gov/CME_list/NOAA/org_events_text"


def download_text(url: str, retries: int = 3, timeout: int = 30) -> str:
    if requests is None:
        raise RuntimeError(
            "The 'requests' package is required for NOAA downloading. "
            "Install it with: pip install requests"
        )

    last = None
    headers = {"User-Agent": "SolarFlareResearch/2022-full-year-evaluation"}

    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=timeout, headers=headers)
            r.raise_for_status()
            if len(r.text.strip()) < 100:
                raise RuntimeError("Downloaded report is unexpectedly short.")
            return r.text
        except Exception as exc:
            last = exc
            time.sleep(1.0 + attempt)

    raise RuntimeError(f"Could not download {url}: {last}")


def fetch_noaa_reports(raw_dir: Path) -> pd.DataFrame:
    raw_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for month in range(1, 13):
        ndays = calendar.monthrange(YEAR, month)[1]

        for day in range(1, ndays + 1):
            date = pd.Timestamp(year=YEAR, month=month, day=day)
            ymd = date.strftime("%Y%m%d")
            target = raw_dir / f"{ymd}events.txt"

            official = (
                f"{NCEI_BASE}/{YEAR}/{month:02d}/{ymd}events.txt"
            )
            fallback = f"{CDAW_BASE}/{YEAR}/{ymd}events.txt"

            source_url = None

            if not target.exists() or target.stat().st_size < 100:
                text = None

                for url in [official, fallback]:
                    try:
                        text = download_text(url)
                        source_url = url
                        break
                    except Exception:
                        continue

                if text is None:
                    raise RuntimeError(
                        f"Could not download NOAA report for {ymd} "
                        f"from NCEI or CDAW."
                    )

                target.write_text(text, encoding="utf-8")
            else:
                # Prefer official source in metadata when using a cached file.
                source_url = official

            rows.extend(parse_noaa_report(target, date, source_url))

        print(f"Downloaded/parsed NOAA reports through {YEAR}-{month:02d}")

    catalog = pd.DataFrame(rows)

    if catalog.empty:
        raise RuntimeError("No XRA events were parsed from NOAA reports.")

    catalog = catalog.sort_values(
        ["peak_time", "report_date", "noaa_event_number", "event_id"]
    ).reset_index(drop=True)

    return catalog


XRA_RE = re.compile(
    r"^\s*(\d+)\s*(\+)?\s+"
    r"(\S+)\s+(\S+)\s+(\S+)\s+"
    r"(\S+)\s+(\S+)\s+XRA\s+(\S+)\s+"
    r"([ABCMX]\d+(?:\.\d+)?)\s+(\S+)"
    r"(?:\s+(\d+))?\s*$"
)


def parse_time_token(token: str):
    if token == "////":
        return None, ""

    digits = "".join(c for c in token if c.isdigit())
    qualifier = "".join(c for c in token if not c.isdigit())

    if len(digits) != 4:
        return None, qualifier

    hour = int(digits[:2])
    minute = int(digits[2:])

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None, qualifier

    return (hour, minute), qualifier


def timestamp_from_hhmm(report_date, hhmm):
    if hhmm is None:
        return pd.NaT

    hour, minute = hhmm
    return pd.Timestamp(
        year=report_date.year,
        month=report_date.month,
        day=report_date.day,
        hour=hour,
        minute=minute,
        tz="UTC",
    )


def class_flux(letter: str, magnitude: float) -> float:
    scales = {
        "A": 1e-8,
        "B": 1e-7,
        "C": 1e-6,
        "M": 1e-5,
        "X": 1e-4,
    }
    return scales[letter] * magnitude


def parse_noaa_report(path: Path, report_date, source_url: str):
    text = path.read_text(encoding="utf-8", errors="replace")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    rows = []
    seq_by_group = {}

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if " XRA " not in raw_line:
            continue

        m = XRA_RE.match(raw_line)
        if not m:
            # Keep parsing strict so a format change is visible.
            raise ValueError(
                f"Unrecognized XRA line in {path.name}, line {line_number}:\n"
                f"{raw_line}"
            )

        (
            event_number,
            plus,
            start_tok,
            peak_tok,
            end_tok,
            observatory,
            quality,
            wavelength,
            flare_class,
            integrated_flux_tok,
            region_tok,
        ) = m.groups()

        start_hhmm, start_qual = parse_time_token(start_tok)
        peak_hhmm, peak_qual = parse_time_token(peak_tok)
        end_hhmm, end_qual = parse_time_token(end_tok)

        # A missing peak cannot be used as an event reference.
        if peak_hhmm is None:
            continue

        start_time = timestamp_from_hhmm(report_date, start_hhmm)
        peak_time = timestamp_from_hhmm(report_date, peak_hhmm)
        end_time = timestamp_from_hhmm(report_date, end_hhmm)

        peak_next_day = False
        end_next_day = False

        if pd.notna(start_time) and peak_time < start_time:
            peak_time += pd.Timedelta(days=1)
            peak_next_day = True

        if pd.notna(end_time):
            chronology_anchor = peak_time if pd.notna(peak_time) else start_time
            if pd.notna(chronology_anchor) and end_time < chronology_anchor:
                end_time += pd.Timedelta(days=1)
                end_next_day = True

        letter = flare_class[0]
        magnitude = float(flare_class[1:])
        integrated_flux = pd.to_numeric(
            integrated_flux_tok, errors="coerce"
        )

        noaa_group = f"SWPC-{report_date.strftime('%Y%m%d')}-{event_number}"
        seq_by_group[noaa_group] = seq_by_group.get(noaa_group, 0) + 1
        seq = seq_by_group[noaa_group]

        event_id = (
            f"{noaa_group}-P{peak_time.strftime('%Y%m%dT%H%M')}"
        )

        rows.append({
            "event_id": event_id,
            "noaa_event_group": noaa_group,
            "sequential_peak_number": seq,
            "report_date": report_date.strftime("%Y-%m-%d"),
            "noaa_event_number": int(event_number),
            "start_time": start_time,
            "peak_time": peak_time,
            "end_time": end_time,
            "class": flare_class,
            "class_letter": letter,
            "class_magnitude": magnitude,
            "class_equivalent_peak_flux_w_m2": class_flux(letter, magnitude),
            "integrated_flux_j_m2": integrated_flux,
            "noaa_region": (
                int(region_tok) if region_tok is not None else np.nan
            ),
            "observatory": observatory,
            "quality": pd.to_numeric(quality, errors="coerce"),
            "preferred_report": bool(plus),
            "start_qualifier": start_qual,
            "peak_qualifier": peak_qual,
            "end_qualifier": end_qual,
            "peak_next_day": peak_next_day,
            "end_next_day": end_next_day,
            "eligible_cmx": letter in {"C", "M", "X"},
            "exclusion_reason": (
                "" if letter in {"C", "M", "X"} else "Below C class"
            ),
            "source_url": source_url,
            "source_file": path.name,
            "source_line": line_number,
            "source_sha256": sha,
            "raw_line": raw_line,
        })

    return rows


# ============================================================
# GOES INPUT
# ============================================================

def read_goes_full_year(path: Path):
    """
    The supplied ZIP has four identical diode rows per minute.
    Keep quad_diode=0 to avoid holding 2.1M duplicate rows in memory.
    """
    pieces = []
    usecols = ["time", "quad_diode", "xrsb_flux", "xrsb_flag"]

    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError("GOES ZIP must contain exactly one CSV.")

        with z.open(names[0]) as f:
            for chunk in pd.read_csv(
                f, usecols=usecols, chunksize=250000
            ):
                part = chunk.loc[chunk["quad_diode"].eq(0)].copy()
                pieces.append(part)

    frame = pd.concat(pieces, ignore_index=True)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.sort_values("time").drop_duplicates("time").set_index("time")

    expected = 365 * 24 * 60
    if len(frame) != expected:
        print(
            f"WARNING: found {len(frame):,} unique minute rows; "
            f"expected {expected:,}. Monthly regularization will fill "
            "missing timestamps with NaN."
        )

    return frame


def regularize(frame: pd.DataFrame, month: str):
    start = pd.Timestamp(month + "-01", tz="UTC")
    end = start + pd.offsets.MonthBegin(1)
    grid = pd.date_range(start, end, freq="min", inclusive="left")
    return frame.loc[(frame.index >= start) & (frame.index < end)].reindex(grid)


# ============================================================
# CAUSAL WAVELET PIPELINE
# ============================================================

def causal_gap_fill(raw: np.ndarray, cfg: Config):
    raw = np.asarray(raw, dtype=float)

    observed = np.isfinite(raw) & (raw >= 0)
    used = np.where(observed, raw, np.nan)

    availability = np.arange(len(raw), dtype=np.int64)
    availability[~observed] = len(raw) + 1

    interpolated = np.zeros(len(raw), dtype=bool)

    prev = -1
    for i in np.flatnonzero(observed):
        missing = i - prev - 1

        if (
            prev >= 0
            and 0 < missing <= cfg.interpolate_max_missing_minutes
        ):
            used[prev + 1:i] = np.linspace(
                raw[prev], raw[i], missing + 2
            )[1:-1]
            availability[prev + 1:i] = i
            interpolated[prev + 1:i] = True

        prev = i

    return used, observed, availability, interpolated


def compute_wavelet_decisions(part: pd.DataFrame, cfg=CFG):
    raw = part["xrsb_flux"].to_numpy(dtype=float)
    used, observed, availability, interpolated = causal_gap_fill(raw, cfg)

    n = len(part)
    ticks = np.arange(0, n, cfg.decision_minutes)

    energy = np.full(len(ticks), np.nan)

    for j, t in enumerate(ticks):
        left = t - cfg.window_minutes + 1

        if left < 0 or not observed[t]:
            continue

        window = used[left:t + 1]

        if (
            not np.isfinite(window).all()
            or np.max(availability[left:t + 1]) > t
        ):
            continue

        details = pywt.wavedec(
            window,
            cfg.wavelet,
            mode=cfg.extension_mode,
            level=cfg.level,
        )[1]

        energy[j] = float(np.dot(details, details))

    pred = np.full(len(ticks), np.nan)
    det = np.full(len(ticks), np.nan)
    rank = np.full(len(ticks), np.nan)
    history_count = np.zeros(len(ticks), dtype=int)

    history = deque()

    for j, t in enumerate(ticks):
        while history and history[0][0] < t - cfg.horizon_minutes:
            history.popleft()

        if np.isfinite(energy[j]):
            history.append((t, energy[j]))

        if history:
            values = np.array([v for _, v in history])

            pred[j], det[j] = np.quantile(
                values,
                [cfg.prediction_quantile, cfg.detection_quantile],
                method=cfg.quantile_method,
            )

            history_count[j] = len(values)

            if np.isfinite(energy[j]):
                rank[j] = np.mean(values <= energy[j])

    decisions = pd.DataFrame({
        "time": part.index[ticks],
        "minute_index": ticks,
        "flux": raw[ticks],
        "energy": energy,
        "prediction_threshold": pred,
        "detection_threshold": det,
        "priority_rank": rank,
        "threshold_history_count": history_count,
        "observed_right_edge": observed[ticks],
        "feature_valid": np.isfinite(energy),
        "after_warmup": ticks >= cfg.warmup_minutes,
    })

    decisions["decision_eligible"] = (
        decisions["feature_valid"]
        & decisions["after_warmup"]
    )

    decisions["prediction_above"] = (
        decisions["decision_eligible"]
        & (energy > pred)
    )

    decisions["detection_above"] = (
        decisions["decision_eligible"]
        & (energy > det)
    )

    return decisions


def eventize_wavelet(
    decisions: pd.DataFrame,
    stream: str,
    cfg=CFG,
    month_end=None,
):
    events = []
    active = None
    pending = None
    segment = 0

    threshold = stream + "_threshold"
    above_col = stream + "_above"

    for r in decisions.to_dict("records"):
        t = r["time"]

        if not r["decision_eligible"]:
            if active is not None:
                active["end_time"] = t
                active["right_censored"] = False

            active = None
            pending = None
            segment += 1
            continue

        if not r[above_col]:
            if active is not None:
                active["end_time"] = t
                active["right_censored"] = False

            active = None
            pending = None
            continue

        if active is not None:
            active["end_time"] = min(
                t + pd.Timedelta(minutes=cfg.decision_minutes),
                month_end,
            )
            active["right_censored"] = True
            continue

        if pending is None:
            pending = t

        elapsed = (t - pending).total_seconds() / 60.0

        if elapsed < cfg.persistence_minutes:
            continue

        if (
            events
            and events[-1]["segment_id"] == segment
            and (t - events[-1]["end_time"]).total_seconds() / 60.0
            <= cfg.merge_gap_minutes
        ):
            active = events[-1]
            active["raw_alerts_merged"] += 1

        else:
            active = {
                "alert_id": (
                    f"{stream[0].upper()}-{t.strftime('%Y%m')}-"
                    f"{len(events)+1:04d}"
                ),
                "stream": stream,
                "start_time": t,
                "crossing_start_time": pending,
                "end_time": t,
                "priority": float(r["priority_rank"]),
                "energy_at_start": float(r["energy"]),
                "threshold_at_start": float(r[threshold]),
                "flux_at_start": float(r["flux"]),
                "raw_alerts_merged": 1,
                "segment_id": segment,
                "right_censored": True,
            }
            events.append(active)

        active["end_time"] = min(
            t + pd.Timedelta(minutes=cfg.decision_minutes),
            month_end,
        )
        active["right_censored"] = True

        pending = None

    return pd.DataFrame(events, columns=ALERT_COLUMNS)


def match_wavelet(
    alerts: pd.DataFrame,
    refs: pd.DataFrame,
    stream: str,
    cfg=CFG,
):
    ordered = alerts.sort_values(["start_time", "alert_id"])
    refs = refs.sort_values(["peak_time", "event_id"]).reset_index(drop=True)

    available = set(range(len(refs)))
    matches = []

    for alert in ordered.to_dict("records"):
        t = alert["start_time"]
        choices = []

        for idx in available:
            ref = refs.iloc[idx]
            lead = (ref["peak_time"] - t).total_seconds() / 60.0

            if stream == "prediction":
                if (
                    cfg.prediction_min_lead_minutes
                    <= lead
                    <= cfg.prediction_max_lead_minutes
                ):
                    choices.append(
                        (lead, ref["peak_time"], str(ref["event_id"]), idx)
                    )
            else:
                if abs(lead) <= cfg.detection_tolerance_minutes:
                    choices.append(
                        (
                            abs(lead),
                            ref["peak_time"],
                            str(ref["event_id"]),
                            idx,
                        )
                    )

        if not choices:
            continue

        _, _, _, idx = min(choices)
        available.remove(idx)
        ref = refs.iloc[idx]

        lead = (ref["peak_time"] - t).total_seconds() / 60.0

        matches.append({
            "alert_id": alert["alert_id"],
            "stream": stream,
            "alert_start_time": t,
            "crossing_start_time": alert["crossing_start_time"],
            "event_id": ref["event_id"],
            "noaa_peak_time": ref["peak_time"],
            "noaa_class": ref["class"],
            "lead_minutes": lead,
            "offset_minutes": -lead,
            "priority": alert["priority"],
            "timing_basis": "confirmed",
        })

    matched = pd.DataFrame(matches, columns=MATCH_COLUMNS)

    return metric_from_matches(alerts, refs, matched, stream), matched


# ============================================================
# GENERIC FORECASTING BASELINES
# ============================================================

def make_baseline_decisions(part, feature, threshold):
    raw = pd.to_numeric(part["xrsb_flux"], errors="coerce").to_numpy(float)
    observed = np.isfinite(raw) & (raw >= 0)

    ticks = np.arange(0, len(part), CFG.decision_minutes)

    feature = np.asarray(feature, dtype=float)
    feat = feature[ticks]

    if np.isscalar(threshold):
        thr = np.full(len(ticks), float(threshold))
    else:
        thr = np.asarray(threshold, dtype=float)[ticks]

    eligible = (
        observed[ticks]
        & np.isfinite(feat)
        & np.isfinite(thr)
        & (ticks >= CFG.warmup_minutes)
    )

    return pd.DataFrame({
        "time": part.index[ticks],
        "flux": raw[ticks],
        "feature": feat,
        "threshold": thr,
        "priority_rank": feat,
        "decision_eligible": eligible,
        "above": eligible & (feat > thr),
    })


def eventize_baseline(decisions, label, month_end):
    events = []
    active = None
    pending = None
    segment = 0

    for r in decisions.to_dict("records"):
        t = r["time"]

        if not r["decision_eligible"]:
            if active is not None:
                active["end_time"] = t
            active = None
            pending = None
            segment += 1
            continue

        if not r["above"]:
            if active is not None:
                active["end_time"] = t
            active = None
            pending = None
            continue

        if active is not None:
            active["end_time"] = min(
                t + pd.Timedelta(minutes=CFG.decision_minutes),
                month_end,
            )
            continue

        if pending is None:
            pending = t

        elapsed = (t - pending).total_seconds() / 60.0

        if elapsed < CFG.persistence_minutes:
            continue

        if (
            events
            and events[-1]["segment_id"] == segment
            and (t - events[-1]["end_time"]).total_seconds() / 60.0
            <= CFG.merge_gap_minutes
        ):
            active = events[-1]
            active["raw_alerts_merged"] += 1
        else:
            active = {
                "alert_id": (
                    f"{label}-{t.strftime('%Y%m')}-{len(events)+1:04d}"
                ),
                "start_time": t,
                "end_time": t,
                "segment_id": segment,
                "raw_alerts_merged": 1,
            }
            events.append(active)

        active["end_time"] = min(
            t + pd.Timedelta(minutes=CFG.decision_minutes),
            month_end,
        )
        pending = None

    return pd.DataFrame(events)


def match_prediction_baseline(alerts, refs):
    refs = refs.sort_values(["peak_time", "event_id"]).reset_index(drop=True)
    alerts = alerts.sort_values(["start_time", "alert_id"]).reset_index(drop=True)

    used = np.zeros(len(refs), dtype=bool)
    matches = []

    for alert in alerts.to_dict("records"):
        t = alert["start_time"]

        for j, ref in refs.iterrows():
            if used[j]:
                continue

            lead = (ref["peak_time"] - t).total_seconds() / 60.0

            if lead < CFG.prediction_min_lead_minutes:
                continue

            if lead > CFG.prediction_max_lead_minutes:
                break

            used[j] = True
            matches.append({
                "alert_id": alert["alert_id"],
                "event_id": ref["event_id"],
                "alert_start_time": t,
                "noaa_peak_time": ref["peak_time"],
                "lead_minutes": lead,
            })
            break

    matched = pd.DataFrame(matches)

    return metric_from_matches(
        alerts, refs, matched, "prediction"
    ), matched


def sma_ratio(part, window):
    s = pd.to_numeric(part["xrsb_flux"], errors="coerce")
    baseline = s.shift(1).rolling(
        window,
        min_periods=window,
    ).mean()
    return (s / baseline).to_numpy(float)


def ewma_ratio(part, span):
    s = pd.to_numeric(part["xrsb_flux"], errors="coerce")
    baseline = (
        s.shift(1)
        .ewm(
            span=span,
            adjust=False,
            ignore_na=True,
            min_periods=span,
        )
        .mean()
    )
    return (s / baseline).to_numpy(float)


def log_slope(part, window):
    flux = pd.to_numeric(
        part["xrsb_flux"], errors="coerce"
    ).to_numpy(float)

    valid = np.isfinite(flux) & (flux > 0)

    y = np.full(len(flux), np.nan)
    y[valid] = np.log10(flux[valid])

    x = np.arange(window, dtype=float)
    x -= x.mean()
    denom = np.sum(x * x)

    y0 = np.where(np.isfinite(y), y, 0.0)
    dots = np.correlate(y0, x, mode="valid")

    counts = np.convolve(
        valid.astype(int),
        np.ones(window, dtype=int),
        mode="valid",
    )

    out = np.full(len(flux), np.nan)
    vals = dots / denom
    vals[counts < window] = np.nan
    out[window - 1:] = vals

    return out


# ============================================================
# METRICS
# ============================================================

def metric_from_matches(alerts, refs, matched, stream):
    tp = len(matched)
    fp = len(alerts) - tp
    fn = len(refs) - tp

    precision = tp / len(alerts) if len(alerts) else 0.0
    recall = tp / len(refs) if len(refs) else np.nan

    f1 = (
        2 * tp / (2 * tp + fp + fn)
        if (2 * tp + fp + fn)
        else np.nan
    )

    out = {
        "alerts_issued": len(alerts),
        "noaa_cmx_events": len(refs),
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "precision": precision,
        "recall": recall,
        "F1": f1,
        "median_lead_minutes": np.nan,
        "median_abs_detection_offset_minutes": np.nan,
    }

    if tp and stream == "prediction":
        out["median_lead_minutes"] = float(
            np.median(matched["lead_minutes"])
        )

    if tp and stream == "detection":
        out["median_abs_detection_offset_minutes"] = float(
            np.median(np.abs(matched["offset_minutes"]))
        )

    return out


def pool_metrics(monthly, method, exclude_april=False):
    d = monthly.loc[monthly["method"].eq(method)].copy()

    if exclude_april:
        d = d.loc[~d["month"].eq("2022-04")]

    tp = int(d["TP"].sum())
    fp = int(d["FP"].sum())
    fn = int(d["FN"].sum())

    precision = tp / (tp + fp) if tp + fp else np.nan
    recall = tp / (tp + fn) if tp + fn else np.nan
    f1 = (
        2 * tp / (2 * tp + fp + fn)
        if 2 * tp + fp + fn
        else np.nan
    )

    return {
        "method": method,
        "period": (
            "Jan-Dec 2022"
            if not exclude_april
            else "11 non-April months"
        ),        "TP": tp,
        "FP": fp,
        "FN": fn,
        "precision": precision,
        "recall": recall,
        "F1": f1,
    }


# ============================================================
# FULL-YEAR EVALUATION
# ============================================================

def evaluate_full_year(goes, catalog, output_dir):
    months = [f"{YEAR}-{m:02d}" for m in range(1, 13)]

    rows = []
    all_matches = {}

    for month in months:
        print("\nProcessing", month)

        part = regularize(goes, month)

        start = pd.Timestamp(month + "-01", tz="UTC")
        end = start + pd.offsets.MonthBegin(1)

        refs = catalog.loc[
            (catalog["peak_time"] >= start)
            & (catalog["peak_time"] < end)
            & (catalog["class_letter"].isin(["C", "M", "X"]))
            & (
                catalog["peak_time"]
                >= start + pd.Timedelta(minutes=CFG.warmup_minutes)
            )
        ].copy()

        # ---------------- Wavelet Prediction / Detection ----------------
        decisions = compute_wavelet_decisions(part, CFG)

        for stream, formal_name in [
            ("prediction", "Wavelet Prediction"),
            ("detection", "Wavelet Detection"),
        ]:
            alerts = eventize_wavelet(
                decisions, stream, CFG, month_end=end
            )
            metric, matched = match_wavelet(
                alerts, refs, stream, CFG
            )

            all_matches[(month, formal_name)] = matched

            rows.append({
                "month": month,
                "method": formal_name,
                **metric,
            })

        # ---------------- Forecasting baselines ----------------
        baseline_specs = [
            (
                "SMA (105 min, ×1.31; 10–90 min)",
                sma_ratio(part, 105),
                1.31,
                "SMA105",
            ),
            (
                "SMA (10 min, ×1.10; 10–90 min)",
                sma_ratio(part, 10),
                1.10,
                "SMA10",
            ),
            (
                "EWMA (10 min, ×1.05; 10–90 min)",
                ewma_ratio(part, 10),
                1.05,
                "EWMA",
            ),
            (
                "Slope (20 min, log-flux; 10–90 min)",
                log_slope(part, 20),
                SLOPE_THRESHOLD_DEX_PER_MIN,
                "SLOPE",
            ),
        ]

        for formal_name, feature, threshold, label in baseline_specs:
            bdec = make_baseline_decisions(
                part, feature, threshold
            )
            alerts = eventize_baseline(
                bdec, label, month_end=end
            )
            metric, matched = match_prediction_baseline(
                alerts, refs
            )

            all_matches[(month, formal_name)] = matched

            rows.append({
                "month": month,
                "method": formal_name,
                **metric,
            })

    monthly = pd.DataFrame(rows)

    # Add pooled median lead from individual matches.
    pooled_rows = []

    for method in monthly["method"].unique():
        for exclude_april in [False, True]:
            rec = pool_metrics(
                monthly,
                method,
                exclude_april=exclude_april,
            )

            months_used = [
                m for m in months
                if not (exclude_april and m == "2022-04")
            ]

            lead_values = []
            det_offsets = []

            for month in months_used:
                matched = all_matches[(month, method)]

                if matched is None or matched.empty:
                    continue

                if "lead_minutes" in matched:
                    lead_values.extend(
                        matched["lead_minutes"].dropna().tolist()
                    )

                if "offset_minutes" in matched:
                    det_offsets.extend(
                        np.abs(
                            matched["offset_minutes"].dropna()
                        ).tolist()
                    )

            rec["median_lead_minutes"] = (
                float(np.median(lead_values))
                if lead_values and "Detection" not in method
                else np.nan
            )

            rec["median_abs_detection_offset_minutes"] = (
                float(np.median(det_offsets))
                if det_offsets and "Detection" in method
                else np.nan
            )

            pooled_rows.append(rec)

    pooled = pd.DataFrame(pooled_rows)

    monthly.to_csv(
        output_dir / "monthly_metrics_Jan_Dec_2022.csv",
        index=False,
    )
    pooled.to_csv(
        output_dir / "pooled_metrics_2022.csv",
        index=False,
    )

    # Reference event counts.
    ref_counts = (
        catalog.loc[catalog["class_letter"].isin(["C", "M", "X"])]
        .assign(month=lambda x: x["peak_time"].dt.strftime("%Y-%m"))
        .groupby(["month", "class_letter"])
        .size()
        .unstack(fill_value=0)
        .reindex(months, fill_value=0)
        .reset_index()
    )
    ref_counts["total_CMX"] = (
        ref_counts.get("C", 0)
        + ref_counts.get("M", 0)
        + ref_counts.get("X", 0)
    )
    ref_counts.to_csv(
        output_dir / "NOAA_CMX_counts_by_month_2022.csv",
        index=False,
    )

    # F1 comparison figure for forecasting methods.
    forecast_methods = [
        "Wavelet Prediction",
        "SMA (105 min, ×1.31; 10–90 min)",
        "SMA (10 min, ×1.10; 10–90 min)",
        "EWMA (10 min, ×1.05; 10–90 min)",
        "Slope (20 min, log-flux; 10–90 min)",
    ]

    fig, ax = plt.subplots(figsize=(10.5, 5.2))

    for method in forecast_methods:
        d = monthly.loc[monthly["method"].eq(method)].copy()
        ax.plot(
            range(1, 13),
            d["F1"],
            marker="o",
            linewidth=1.4,
            label=method,
        )

    ax.set_xticks(
        range(1, 13),
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    )
    ax.set_xlabel("Month (2022)")
    ax.set_ylabel("F1 score")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7.3, frameon=True)
    fig.tight_layout()
    fig.savefig(
        output_dir / "forecast_F1_Jan_Dec_2022.png",
        dpi=600,
        bbox_inches="tight",
    )
    plt.close(fig)

    # Wavelet stream monthly F1 figure.
    fig, ax = plt.subplots(figsize=(9.5, 4.8))

    for method in ["Wavelet Prediction", "Wavelet Detection"]:
        d = monthly.loc[monthly["method"].eq(method)].copy()
        ax.plot(
            range(1, 13),
            d["F1"],
            marker="o",
            linewidth=1.5,
            label=method,
        )

    ax.set_xticks(
        range(1, 13),
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    )
    ax.set_xlabel("Month (2022)")
    ax.set_ylabel("F1 score")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=True)
    fig.tight_layout()
    fig.savefig(
        output_dir / "wavelet_prediction_detection_F1_Jan_Dec_2022.png",
        dpi=600,
        bbox_inches="tight",
    )
    plt.close(fig)

    return monthly, pooled, ref_counts


# ============================================================
# MAIN
# ============================================================

def main():
    output = Path(OUTPUT_FOLDER).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    goes_zip = locate_goes_zip()

    print("\n1/4 Reading full-year GOES data...")
    goes = read_goes_full_year(goes_zip)

    print(
        "GOES minute coverage:",
        goes.index.min(),
        "to",
        goes.index.max(),
        f"({len(goes):,} minute rows)",
    )

    print("\n2/4 Downloading/parsing NOAA event reports...")
    raw_dir = output / "NOAA_2022_daily_event_reports"
    catalog = fetch_noaa_reports(raw_dir)

    catalog.to_csv(
        output / "NOAA_XRA_context_2022.csv",
        index=False,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )

    cmx = catalog.loc[
        catalog["class_letter"].isin(["C", "M", "X"])
    ].copy()

    cmx.to_csv(
        output / "NOAA_CMX_reference_2022.csv",
        index=False,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )

    print(
        f"Parsed {len(catalog):,} XRA reports, including "
        f"{len(cmx):,} C/M/X reference events."
    )

    print("\n3/4 Running Jan-Dec 2022 evaluation...")
    monthly, pooled, counts = evaluate_full_year(
        goes, catalog, output
    )

    print("\n4/4 Finished.")
    print("\nFull-year pooled results:")
    print(
        pooled.loc[
            pooled["period"].eq("Jan-Dec 2022")
        ].to_string(index=False)
    )

    print("\nFiles saved to:")
    print(output)


if __name__ == "__main__":
    main()