# Causal Wavelet-Energy Solar Flare Detection and Prediction

Reproducibility repository for the conference paper **Detection and Short-Term Prediction of Solar Flares Using a Causal Wavelet-Energy Feature**.

The reference configuration is evaluated on January-December 2022 and then frozen and applied without parameter retuning to January-December 2023.

## Main results

| Evaluation | Precision | Recall | F1 | Timing |
|---|---:|---:|---:|---:|
| 2022 Prediction | 0.293 | 0.396 | 0.336 | 45-min median lead |
| 2022 Detection | 0.577 | 0.337 | 0.425 | 3-min median absolute offset |
| 2023 Prediction (OOS) | 0.400 | 0.379 | 0.389 | 43-min median lead |
| 2023 Detection (OOS) | 0.744 | 0.304 | 0.432 | 3-min median absolute offset |

The pre-defined T=12 h mitigation reduced 2022 Prediction false positives from 2205 to 1968 (10.7%). Applied unchanged in 2023, it reduced false positives from 1855 to 1703 (8.2%), with a small recall/F1 tradeoff.

## Important comparability note

The alert-generation parameters are frozen for the 2023 temporal out-of-sample test, but the two years use different NOAA flare-reference products for scoring:

- **2022:** NOAA/SWPC daily Solar Event Reports (XRA entries).
- **2023:** NOAA/NCEI GOES XRS Level-2 science flare report.

Accordingly, differences between 2022 and 2023 metrics can reflect both solar-activity differences and catalog construction. The higher 2023 precision is not interpreted as an improvement caused solely by temporal generalization. See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Repository structure

- `code/` — input preparation, 2022 analysis/ablation, 2023 alert generation, and metric verification.
- `data/reference/` — committed flare-reference catalogs used for audit/scoring.
- `data/coverage/` — GOES coverage summaries.
- `data/raw/` — local location for large public GOES inputs (not committed).
- `results/2022/` — main metrics, monthly outputs, ablation, false-positive analysis, and mitigation.
- `results/2023/` — saved frozen-alert outputs and out-of-sample metrics.
- `docs/` — configuration, provenance, and reproduction instructions.

## Reference configuration

- GOES-16 XRS 1-8 Å flux, 1-min cadence
- db2 wavelet, level 3
- PyWavelets `symmetric` boundary extension inside each right-aligned 30-min window
- 30-min right-aligned feature window
- 2-min decision cadence
- 6-h trailing percentile history
- Prediction percentile 0.80
- Detection percentile 0.95
- 120-min monthly warm-up
- 4-min persistence span
- merge gap <= 12 min
- Prediction match: 10-90 min before NOAA peak
- Detection match: +/-10 min around NOAA peak
- greedy one-to-one matching
- C/M/X flare classes

The mitigation changes only the trailing history from T=6 h to T=12 h.

## Quick reproduction

Python 3.12+ is recommended.

```bash
pip install -r requirements.txt
python code/prepare_goes_inputs.py
python code/run_2022_full_analysis.py
python code/run_2022_ablation.py
python code/run_2023_alerts.py
python code/verify_2023_metrics.py
```

See [docs/RUN_ORDER.md](docs/RUN_ORDER.md) for details.

## Data availability

Large GOES NetCDF inputs are public NOAA/NCEI files and are intentionally not duplicated in Git. `code/prepare_goes_inputs.py` downloads them from the official archive and builds the compact 2022 ZIP expected by the preserved analysis code.

The small flare-reference catalogs, 2022 monthly metrics, 2022/2023 coverage summaries, and 2023 alert-event files needed to audit the reported scoring are committed directly in this repository.

## Reproducibility notes

- `code/run_2022_full_analysis.py` reproduces the full 2022 wavelet and baseline analysis.
- `code/run_2022_ablation.py` reproduces the one-factor-at-a-time wavelet sensitivity table.
- `code/run_2023_alerts.py` regenerates the frozen T=6 h and pre-defined T=12 h 2023 alert files from the raw GOES-16 NetCDF without using flare labels.
- `code/verify_2023_metrics.py` scores those alerts against the committed 2023 flare report.

Each calendar month is processed independently. Therefore, an alert near a month boundary is evaluated within that month's scoring window and is not matched across calendar-month boundaries.

## License

Code is released under the MIT License. NOAA source data retain their original public-data terms and provenance.

## Citation

Please cite the associated conference paper. Final bibliographic details can be added after acceptance/publication.
