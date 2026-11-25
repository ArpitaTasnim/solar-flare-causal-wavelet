# Final experimental configuration

## Reference model
- Wavelet: db2
- DWT level: 3
- Wavelet extension mode in preserved 2022 runner: symmetric
- Input feature window K: 30 min, right-aligned
- Decision cadence: 2 min
- Streaming percentile horizon T: 6 h
- Warm-up: 120 min per calendar month
- Prediction percentile Qpred: 0.80
- Detection percentile Qdet: 0.95
- Persistence: 4 min (two decision intervals)
- Same-stream alert merge gap: <=12 min
- Prediction event match: NOAA peak 10-90 min after alert start
- Detection event match: +/-10 min around NOAA peak
- Matching: greedy one-to-one
- Primary labels: C/M/X

## Exploratory mitigation
The mitigation retains db2 and all other settings but changes the trailing percentile history from T=6 h to T=12 h.

## Baselines in the final 2022 comparison
- SMA 105 min, multiplier 1.31
- SMA 10 min, multiplier 1.10
- EWMA span 10 min, multiplier 1.05
- Log-flux slope over 20 min, threshold 0.0035452873815516642 dex/min

All forecasting baselines use the same 2-min decision cadence, warm-up, persistence, merging, and 10-90-min Prediction matching protocol.
