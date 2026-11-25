# Data provenance

## GOES XRS flux input

Both years use the GOES-16 XRS Level-2 **1-minute average science product** and the 1–8 Å (`xrsb_flux`) channel.

Official NOAA/NCEI directory:

https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/goes16/l2/data/xrsf-l2-avg1m_science/

Files used by the reproducibility workflow:

- 2022: `sci_xrsf-l2-avg1m_g16_y2022_v2-2-1.nc`
- 2023: `sci_xrsf-l2-avg1m_g16_y2023_v2-2-1.nc`

The original 2022 working archive `GOES_2022_FULL.zip` was a flattened CSV representation. The analysis only reads `time`, `quad_diode`, `xrsb_flux`, and `xrsb_flag`, then retains `quad_diode == 0`. `code/prepare_goes_inputs.py` downloads the official NetCDF and creates an analysis-equivalent compact `GOES_2022_FULL.zip`.

## 2022 flare-reference catalog

The 2022 evaluation uses NOAA/SWPC daily Solar Event Reports, parsing XRA lines and retaining C/M/X events. The parser and official/fallback source URLs are in `code/run_2022_full_analysis.py`.

The parsed catalog used for audit/scoring is committed at:

`data/reference/2022/NOAA_CMX_reference_2022.csv`

## 2023 flare-reference catalog

The 2023 temporal out-of-sample scoring uses the NOAA/NCEI GOES XRS Level-2 science flare report:

`sci_xrsf-l2-flrpt_geo_y2023_v1-0-1.csv`

Official NOAA/NCEI directory:

https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/l2/data/xrsf-l2-flrpt_science/csv/

The exact CSV used for scoring is committed at:

`data/reference/2023/sci_xrsf-l2-flrpt_geo_y2023_v1-0-1.csv`

## Important catalog comparability note

The 2022 and 2023 evaluations do **not** use the identical flare-reference product format:

- 2022: SWPC daily Solar Event Reports (XRA entries).
- 2023: GOES XRS Level-2 science flare report.

Therefore, the 2023 results provide a frozen-parameter temporal out-of-sample test, but differences between 2022 and 2023 metrics may reflect both year-to-year solar conditions **and** differences in the reference catalog construction. The higher 2023 precision should not be interpreted as evidence of improvement caused solely by temporal generalization.

## Label use and causality

Reference flare labels are used only for scoring/matching. They are not used to generate wavelet features, thresholds, or alert states.

## Data cleaning details

The causal wavelet implementation treats non-finite and negative `xrsb_flux` samples as unavailable. Gaps of at most 2 min are filled only when the required bracketing observation has arrived; longer gaps remain unavailable.

The committed 2022 runner reads `xrsb_flag` from the flattened input but does not use the quality flag as an additional exclusion rule. The 2023 raw-to-alert generator likewise uses the flux values and treats invalid/negative flux as unavailable.

The forecasting baselines operate on the raw flux series and do not use the wavelet pipeline's short-gap interpolation.

## Large-file policy

The large GOES NetCDF files are not committed to Git. Run:

```bash
python code/prepare_goes_inputs.py
```

to download the public NOAA/NCEI inputs into the expected repository paths.
