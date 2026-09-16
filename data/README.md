# NYC yellow taxi sample

`yellow_tripdata_sample.parquet` contains 50,000 actual TLC yellow taxi trips from January 2024. It is a deterministic sample, not an invented dataset or full-month totals. `taxi_zone_lookup.csv` is copied verbatim from the BADM 554 course data folder.

Source files supplied locally:

- `/Users/vishal/teaching/badm554/semesters/fall2026-online/data/yellow_tripdata_2024-01.parquet`
- `/Users/vishal/teaching/badm554/semesters/fall2026-online/data/taxi_zone_lookup.csv`

The preparation follows the filtering conditions in the course's `learner-files/sql/M4I6-taxi-star.sql`. It keeps January pickups, positive durations up to 720 minutes, positive distances up to 100 miles, and positive fares up to 500 dollars. Before filtering, DuckDB assigns the original Parquet row offset. The sample takes 50,000 cleaned trips ordered by MD5 of that offset (offset breaks ties), then writes them ordered by offset. No random seed or machine-specific hash function is involved.

`sample_manifest.json` records source/sample/lookup SHA-256 hashes, the exact sampling SQL, row count and DuckDB version. `source_row_number` is the stable original trip identity, not an index into the sample. The sample retains every raw source column. The package projects the fields needed for counts and joins pickup zone information in DuckDB.

To reproduce the sample from a local full extract:

```sh
FIGUREFLOW_TAXI_PARQUET=/path/to/yellow_tripdata_2024-01.parquet .venv/bin/python scripts/build_sample.py
```

The full extract is not committed. `data/*.parquet` is ignored except for this explicitly named sample. Tests and the default demo use only committed files. No service, download or API key is needed after installation.
