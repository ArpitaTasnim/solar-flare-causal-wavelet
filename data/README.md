# Data layout

Large GOES scientific files are downloaded from NOAA/NCEI rather than committed to Git.

Expected local layout:

```text
data/
  raw/
    2022/
      sci_xrsf-l2-avg1m_g16_y2022_v2-2-1.nc
      GOES_2022_FULL.zip
    2023/
      sci_xrsf-l2-avg1m_g16_y2023_v2-2-1.nc
  reference/
    2022/
      NOAA_CMX_reference_2022.csv
    2023/
      sci_xrsf-l2-flrpt_geo_y2023_v1-0-1.csv
  coverage/
    GOES_2022_full_year_coverage_summary.csv
    GOES_2023_coverage_summary.csv
```

Prepare the large GOES inputs with:

```bash
python code/prepare_goes_inputs.py
```

The reference catalogs and coverage summaries are created by the preparation/analysis scripts from the official NOAA sources. See `docs/DATA_SOURCES.md` for provenance and the important 2022-vs-2023 catalog comparability note.
