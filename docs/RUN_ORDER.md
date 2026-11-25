# Suggested run / audit order

## 1. Install dependencies
```bash
pip install -r requirements.txt
```

## 2. Inspect the final configuration
Read `docs/CONFIGURATION.md`.

## 3. Audit the 2022 results
Compare the reported values against:
- `results/2022/pooled_metrics_2022.csv`
- `results/2022/Prediction_ablation_full_year_2022.csv`
- `results/2022/Detection_ablation_full_year_2022.csv`
- `results/2022/False_positive_compact_paper_table_2022.csv`
- `results/2022/Prediction_FP_mitigation_T6_vs_T12_2022.csv`

The preserved local artifact package contains the complete 2022 raw-to-results runner and raw GOES archive.

## 4. Verify the 2023 out-of-sample scoring
Place the official NOAA 2023 flare report and the saved 2023 alert-event CSVs in the paths expected by the script, then run:

```bash
python code/reproduce_2023_metrics_from_saved_alerts.py \
  --data-dir data/raw/2023 \
  --alerts-dir results/2023/out_of_sample \
  --out-dir results/2023/recomputed_verification
```

The pooled output should match `results/2023/pooled_metrics_2023_all_settings.csv`.

## 5. Keep 2023 frozen
Do not retune parameters on 2023. Retuning would invalidate the temporal out-of-sample interpretation.
