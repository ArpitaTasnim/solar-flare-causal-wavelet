# Solar flare analysis and validation

- `prepare_2022_reference.py` — downloads/parses the 2022 NOAA/SWPC C/M/X reference catalog.
- `prepare_goes_inputs.py` — downloads and checksum-verifies the preserved 2022 ZIP, 2023 GOES-16 NetCDF and 2023 NOAA flare-reference CSV.
- `run_2022_full_analysis.py` — full January-December 2022 causal wavelet and baseline analysis.
- `run_2022_ablation.py` — one-factor-at-a-time 2022 sensitivity/ablation analysis.
- `run_2023_alerts.py` — regenerates the frozen 2023 T=6 h and T=12 h alert-event files from raw GOES-16 data without using flare labels.
- `verify_2023_metrics.py` — recomputes the reported 2023 out-of-sample scoring metrics from the alert events and committed NOAA flare-reference catalog.

- `check_reproducibility.py` — checks the committed reference catalogs, alert files and reported metrics.

See `docs/RUN_ORDER.md` for the complete workflow.
