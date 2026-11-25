# Causal Wavelet-Energy Solar Flare Detection and Prediction

Reproducibility repository for the conference paper **Detection and Short-Term Prediction of Solar Flares Using a Causal Wavelet-Energy Feature**.

The reference model was evaluated on January-December 2022 and then frozen and applied without retuning to January-December 2023 for temporal out-of-sample validation.

## Main results

| Evaluation | Precision | Recall | F1 | Timing |
|---|---:|---:|---:|---:|
| 2022 Prediction | 0.293 | 0.396 | 0.336 | 45-min median lead |
| 2022 Detection | 0.577 | 0.337 | 0.425 | 3-min median absolute offset |
| 2023 Prediction (OOS) | 0.400 | 0.379 | 0.389 | 43-min median lead |
| 2023 Detection (OOS) | 0.744 | 0.304 | 0.432 | 3-min median absolute offset |

The pre-defined T=12 h mitigation reduced 2022 Prediction false positives from 2205 to 1968 (10.7%). Applied unchanged in 2023, it reduced false positives from 1855 to 1703 (8.2%), with a small recall/F1 tradeoff.

## Repository structure

- `code/` - preserved analysis/verification scripts.
- `data/` - data provenance and coverage summaries.
- `results/2022/` - main metrics, ablation, false-positive analysis, and mitigation.
- `results/2023/` - frozen out-of-sample metrics and verification outputs.
- `docs/` - configuration and reproduction instructions.

## Reference configuration

- GOES XRS 1-8 Å flux, 1-min cadence
- db2 wavelet, level 3
- 30-min right-aligned feature window
- 2-min decision cadence
- 6-h trailing percentile history
- Prediction percentile 0.80
- Detection percentile 0.95
- 120-min monthly warm-up
- 4-min persistence
- merge gap <= 12 min
- Prediction match: 10-90 min before NOAA peak
- Detection match: +/-10 min around NOAA peak
- greedy one-to-one matching
- C/M/X flare classes

The mitigation changes only the trailing history from T=6 h to T=12 h.

## Reproduction

```bash
pip install -r requirements.txt
```

Then follow [docs/RUN_ORDER.md](docs/RUN_ORDER.md).

## Data availability

The large raw GOES scientific files are not duplicated in the normal Git repository. Their exact filenames, provenance, expected paths, and coverage summaries are documented under `data/` and `docs/DATA_SOURCES.md`.

The complete project archive preserves the raw inputs as well as the derived alert-event files. The repository keeps the compact reproducibility materials and reported result tables suitable for conference review.

## Reproducibility note

The preserved 2022 full-year raw-to-results analysis is in `code/run_2022_full_analysis.py`. The 2023 scoring check is in `code/verify_2023_metrics.py`, which recomputes TP/FP/FN, precision, recall, F1, and timing from the saved alert events and official NOAA flare report.

The exact standalone 2023 raw-NetCDF-to-alert wrapper and a separate full-year ablation batch wrapper were not preserved as independent source files in the available workspace. This repository therefore does not claim those wrappers as archived source code; the fixed configuration and derived outputs are documented transparently.

## Citation

Please cite the associated conference paper. Final bibliographic details can be added after acceptance/publication.
