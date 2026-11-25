# Code

- `prepare_2022_reference.py` — downloads/parses the 2022 NOAA/SWPC C/M/X reference catalog.\n- `prepare_goes_inputs.py` — downloads official NOAA/NCEI GOES-16 XRS science NetCDF files and prepares the compact 2022 ZIP used by the preserved runner.
- `run_2022_full_analysis.py` — full January-December 2022 causal wavelet and baseline analysis.
- `run_2022_ablation.py` — one-factor-at-a-time 2022 sensitivity/ablation analysis.
- `run_2023_alerts.py` — regenerates the frozen 2023 T=6 h and T=12 h alert-event files from raw GOES-16 data without using flare labels.
- `verify_2023_metrics.py` — recomputes the reported 2023 out-of-sample scoring metrics from the alert events and committed NOAA flare-reference catalog.

See `docs/RUN_ORDER.md` for the complete workflow.
