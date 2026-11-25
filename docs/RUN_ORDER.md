# Reproduction / audit order

## 1. Create the environment

Python 3.12+ is recommended.

```bash
pip install -r requirements.txt
```

## 2. Download and prepare the public GOES inputs

```bash
python code/prepare_goes_inputs.py
```

This downloads the official GOES-16 XRS Level-2 1-minute science NetCDF files for 2022 and 2023. It also builds the compact `data/raw/2022/GOES_2022_FULL.zip` consumed by the preserved 2022 runner.

## 3. Re-run the 2022 full-year analysis

```bash
python code/run_2022_full_analysis.py
```

Default regenerated outputs are written under:

`results/2022/generated/`

Compare against committed paper-result files such as:

- `results/2022/pooled_metrics_2022.csv`
- `results/2022/monthly_metrics_Jan_Dec_2022.csv`
- `results/2022/False_positive_compact_paper_table_2022.csv`
- `results/2022/Prediction_FP_mitigation_T6_vs_T12_2022.csv`

The 2022 runner downloads/parses the NOAA/SWPC daily Solar Event Reports. The parsed C/M/X reference catalog used for audit is also committed at `data/reference/2022/NOAA_CMX_reference_2022.csv`.

## 4. Re-run the 2022 sensitivity / ablation analysis

```bash
python code/run_2022_ablation.py
```

Generated files are written under `results/2022/generated_ablation/`. Compare against:

- `results/2022/Prediction_ablation_full_year_2022.csv`
- `results/2022/Detection_ablation_full_year_2022.csv`

## 5. Generate the frozen 2023 alerts from raw GOES data

```bash
python code/run_2023_alerts.py
```

This generates:

- `results/2023/out_of_sample/wavelet_alerts_2023_Reference_T6.csv`
- `results/2023/out_of_sample/wavelet_alerts_2023_Mitigation_T12.csv`

No 2023 flare labels are used during alert generation.

Expected alert totals:

| Setting | Prediction | Detection |
|---|---:|---:|
| Reference_T6 | 3092 | 1338 |
| Mitigation_T12 | 2896 | 1102 |

## 6. Verify the 2023 scoring

```bash
python code/verify_2023_metrics.py
```

The script uses:

- the saved/generated 2023 alert CSVs under `results/2023/out_of_sample/`;
- `data/reference/2023/sci_xrsf-l2-flrpt_geo_y2023_v1-0-1.csv`.

Recomputed metrics are written under:

`results/2023/recomputed_verification/`

The pooled results should match `results/2023/pooled_metrics_2023_all_settings.csv`.

## 7. Interpretation caution

The 2023 alert-generation parameters are frozen, but the **scoring catalog is not the same product format as in 2022**. See `docs/DATA_SOURCES.md`. Do not interpret the 2022-to-2023 precision difference as purely a model-generalization improvement.

## 8. Causal timing details

The 4-min persistence setting means the feature must remain above threshold over a 4-min elapsed span at the 2-min decision cadence. In the implementation this corresponds to above-threshold decisions at the crossing time, +2 min, and +4 min. Matching and lead time use the confirmed alert `start_time` (the +4-min confirmation time); `crossing_start_time` is retained separately in the alert CSVs.
