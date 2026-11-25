# Data layout

Large raw scientific files are not committed to the normal Git repository.

Expected local layout:

```text
data/
  raw/
    2022/
      GOES_2022_FULL.zip
    2023/
      sci_xrsf-l2-avg1m_g16_y2023_v2-2-1.nc
      sci_xrsf-l2-flrpt_geo_y2023_v1-0-1.csv
  coverage/
    GOES_2022_full_year_coverage_summary.csv
    GOES_2023_coverage_summary.csv
```

The raw files are preserved in the complete local reproducibility package. See `docs/DATA_SOURCES.md` for provenance and evaluation rules.


## Coverage summaries

The `data/coverage/` directory contains compact coverage summaries for the GOES datasets used in the study.
