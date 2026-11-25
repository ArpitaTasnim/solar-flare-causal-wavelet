# Data provenance

## 2022 GOES XRS
The preserved full-year 2022 GOES XRS input archive used by the project is named `GOES_2022_FULL.zip`. The final main analysis reads the 1-8 Å (`xrsb_flux`) series and processes calendar months independently.

The parsed NOAA/SWPC 2022 C/M/X flare-reference catalog used for scoring is `NOAA_CMX_reference_2022.csv`.

## 2023 GOES XRS
The science-quality 1-min GOES-16 XRS file used for temporal out-of-sample validation is:

`sci_xrsf-l2-avg1m_g16_y2023_v2-2-1.nc`

## 2023 NOAA flare report
The official 2023 GOES flare-report CSV used as the event reference is:

`sci_xrsf-l2-flrpt_geo_y2023_v1-0-1.csv`

## Evaluation rule
Reference flare labels are used only for scoring/matching. They are not used to generate the causal alert feature or thresholds.

Large raw files are intentionally not duplicated in the normal Git repository. Keep them in the local paths described in `data/README.md`.
