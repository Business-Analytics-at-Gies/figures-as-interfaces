# FigureFlow portable artifact format, version 1

Audience: BADM 554 and BDI 513 students using Wolfram notebooks or Python/Colab. Python is the reference implementation. Reading, rendering and selecting from an artifact requires only JSON support and a Vega-Lite renderer, not this package. `artifact.schema.json` is the machine-readable JSON Schema (2020-12); its `$defs.figure` defines the figure shape.

## Artifact envelope

| Key | Meaning |
| --- | --- |
| `format_version` | Integer `1`. Consumers must reject unsupported versions. |
| `artifact_id` | String identifying this exploration. |
| `dataset` | Complete normalized input as JSON row objects. |
| `dataset_hash` | SHA-256 of Python's sorted-key JSON serialization of those rows, used for reference replay integrity. Other consumers can use the rows directly; this hash is not a signature. |
| `source` | Data origin, file hashes, DuckDB preparation SQL and parameters, sample manifest and input schema. |
| `figures` | Dictionary keyed by immutable figure-version ids such as `f0001`. |
| `versions` | Dictionary keyed by artifact-version ids such as `a0001`. Each node has `parents`, `figures`, `links`, `input`, and a UTC `timestamp`. |
| `head` | Current artifact-version id, or null for a new empty ledger. |

`versions[head].figures` maps logical chart ids (such as `chart0002`) to the figure version currently shown. Follow parent links to reconstruct history. A branch names an earlier parent; version dictionaries do not depend on key order. Figure versions are never overwritten by pipeline operations. This is an application history graph, distinct from the Git commits of this project.

## Figure tuple and mapping

Each figure holds the paper's `V`, `C`, `D`, `M` components and explicit `R` mapping:

- `V.spec`: complete Vega-Lite v5 specification, including inline `data.values`. Each aggregate datum has `mark_id`. Render this object directly. Monthly equivalents here are hour-of-day points with a connecting line. Only points and bars are selectable data marks.
- `V.png`: base64-encoded PNG rendered from the spec. Decode as bytes, not a pickle or Python object. `V.summary` is a plain-text account of scope and counts.
- `C.actions`: ordered JSON objects describing the analytical operations. `C.sql`: executable DuckDB SQL, with a temporary `selected` table and final aggregation query. `C.environment`: reference execution versions. `C.visualization_python`: reference-only rendering recipe; foreign-language consumers do not need to execute it.
- `D.rows`: selected original trips, represented by the normalized projection below. `D.schema`: column names to SQL types. `D.results` and `D.result_schema`: grouped values used to draw the figure.
- `M`: `figure_id`, `version_id`, `timestamp`, `operation`, `instruction`, `artifact_id`, `artifact_version`. An operation is `generation`, `extension`, or `coordination`. The artifact-version link points to the state that introduced this figure version.
- `R.mark_to_rows`: dictionary mapping each `mark_id` to every contributing string `row_id`. Aggregated marks can map to thousands of trips. Mark ids are scoped to a figure version, so ids from a stale chart are rejected.

### Input schema

| Field | SQL type | Meaning |
| --- | --- | --- |
| `row_id` | VARCHAR | Zero-based row number in the original January Parquet, encoded as a string. Row identity is assigned before cleaning or sampling. |
| `pickup_zone_id` | BIGINT | Original `PULocationID`, joined to lookup `LocationID`. |
| `pickup_zone` | VARCHAR | Lookup `Zone`. |
| `pickup_borough` | VARCHAR | Lookup `Borough`. |
| `pickup_hour` | BIGINT | Hour 0 through 23 from the TLC local pickup timestamp. |
| `pickup_date` | VARCHAR | ISO date in January 2024. |

The committed Parquet retains all original trip columns plus `source_row_number`. The analytical snapshot intentionally contains the above projection, not every raw taxi attribute. Join `row_id` to `source_row_number` for the remaining raw columns. The source manifest supplies the full-file and sample checksums.

## Selection without importing this package

Language-independent algorithm:

1. Parse the JSON and choose `figures[versions[head].figures[logical_chart_id]]`.
2. Render its `V.spec`. Resolve a brush to the selected inline data's `mark_id` values.
3. Look up each id in `R.mark_to_rows`; reject missing ids and an empty selection.
4. Union the returned row ids. Index `D.rows` by `row_id` and retrieve those rows.
5. To update linked zone charts, find the state's `links` with this logical chart as `source`. Derive distinct pickup hours and boroughs from selected rows; replace those filters in each `action_template` and execute the new action sequence. Preserve January scope and the original borough. Create a new artifact version, retaining prior states.

Python example using only the standard library, equally expressible with Wolfram associations:

```python
import json
with open('taxi-artifact.json') as stream:
    artifact = json.load(stream)
state = artifact['versions'][artifact['head']]
figure = artifact['figures'][state['figures']['chart0001']]
marks = [d['mark_id'] for d in figure['V']['spec']['data']['values']
         if 17 <= d['pickup_hour'] <= 20]
ids = {row_id for mark in marks for row_id in figure['R']['mark_to_rows'][mark]}
rows = [row for row in figure['D']['rows'] if row['row_id'] in ids]
```

The renderer must return selected datum ids, not screenshot coordinates. An interval 17 through 20 selects four hourly marks, across all January dates. This implementation does not ship a browser brush adapter or a Wolfram loader.

## SQL replay and coordination

Load `dataset` into a DuckDB table named `trips` using `source.schema` (or `D.schema` for supplied fixtures). In a fresh connection, execute the chosen figure's `C.sql`. The last statement returns `D.results`; `SELECT * FROM selected ORDER BY row_id` returns `D.rows`. To recover lineage independently, group the `selected` table by `pickup_hour` or `pickup_zone_id` and collect `row_id` in sorted order. No Python package is necessary for these operations.

A coordination link contains `source`, `target` (logical chart ids), `dimensions` (`pickup_hour`, `pickup_borough`) and `action_template`. The template is a language-neutral list, not executable Python. Each version records the input instruction or brush ids and source figure version. Coordination reuses this template without another planner call. Only direct links are supported in this slice.

The reference loader checks graph references and checksums. Replay additionally checks compiler-approved SQL, exact data, mapping, summary and spec. Consumers should treat externally supplied SQL as code and choose their own execution policy. PNG byte identity can vary across machines and fonts; data and Vega-Lite identity are the replay contract.
