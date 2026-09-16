"""Local TLC data preparation, entirely in DuckDB."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import duckdb

CLEAN = """tpep_pickup_datetime >= TIMESTAMP '2024-01-01'
AND tpep_pickup_datetime < TIMESTAMP '2024-02-01'
AND tpep_dropoff_datetime > tpep_pickup_datetime
AND date_diff('minute', tpep_pickup_datetime, tpep_dropoff_datetime) <= 720
AND trip_distance > 0 AND trip_distance <= 100
AND fare_amount > 0 AND fare_amount <= 500"""

SCHEMA = {"row_id": "VARCHAR", "pickup_zone_id": "BIGINT", "pickup_zone": "VARCHAR",
          "pickup_borough": "VARCHAR", "pickup_hour": "BIGINT", "pickup_date": "VARCHAR"}


def file_hash(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bundled_dir() -> Path:
    installed = Path(__file__).parent / 'bundled_data'
    return installed if installed.exists() else Path(__file__).resolve().parents[2] / 'data'


def full_path() -> Path:
    value = os.environ.get('FIGUREFLOW_TAXI_PARQUET')
    if not value or not Path(value).is_file():
        raise ValueError('Set FIGUREFLOW_TAXI_PARQUET to an existing local TLC January 2024 Parquet file')
    return Path(value)


def records(cursor) -> list[dict]:
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _normalize_parquet(path: Path, *, full_data: bool) -> tuple[list[dict], str, Path]:
    directory = bundled_dir()
    lookup = directory / 'taxi_zone_lookup.csv'
    if not path.is_file() or not lookup.is_file():
        raise ValueError('Bundled taxi sample or zone lookup is missing; reinstall the repository package')
    identity = 'file_row_number' if full_data else 'source_row_number'
    sql = f"""SELECT CAST(t.{identity} AS VARCHAR) AS row_id,
       CAST(t.PULocationID AS BIGINT) AS pickup_zone_id,
       z.Zone AS pickup_zone, z.Borough AS pickup_borough,
       CAST(hour(t.tpep_pickup_datetime) AS BIGINT) AS pickup_hour,
       CAST(CAST(t.tpep_pickup_datetime AS DATE) AS VARCHAR) AS pickup_date
FROM read_parquet(?, file_row_number=true) t
JOIN read_csv(?, header=true) z ON t.PULocationID = z.LocationID
WHERE {CLEAN}
ORDER BY t.{identity}"""
    with duckdb.connect(':memory:') as connection:
        connection.execute('SET threads=1')
        rows = records(connection.execute(sql, [str(path), str(lookup)]))
    return rows, sql, lookup


def load_rows(full_data: bool = False) -> tuple[list[dict], dict]:
    directory = bundled_dir()
    path = full_path() if full_data else directory / 'yellow_tripdata_sample.parquet'
    rows, sql, lookup = _normalize_parquet(path, full_data=full_data)
    metadata = {'kind': 'TLC yellow taxi January 2024', 'mode': 'full' if full_data else 'sample',
                'sample_rows': len(rows), 'parquet_sha256': file_hash(path),
                'zone_lookup_sha256': file_hash(lookup), 'preparation_sql': sql,
                'parameters': [path.name, lookup.name], 'schema': SCHEMA}
    manifest = directory / 'sample_manifest.json'
    if not full_data and manifest.exists():
        metadata['sample_manifest'] = json.loads(manifest.read_text())
    return rows, metadata


def load_snapshot(path: Path) -> list[dict]:
    """Load a full analytical snapshot from Parquet (sample) or JSON rows."""
    path = Path(path)
    if path.suffix.lower() == '.parquet':
        # Bundled sample rows carry source_row_number; other TLC exports use file_row_number.
        rows, _, _ = _normalize_parquet(
            path, full_data=path.name != 'yellow_tripdata_sample.parquet'
        )
        return rows
    try:
        return json.loads(path.read_text())
    except OSError as error:
        raise ValueError('Missing or unreadable dataset sidecar') from error


def connection_for(rows: list[dict]):
    """Create a typed local table from the portable JSON snapshot."""
    connection = duckdb.connect(':memory:')
    connection.execute('SET threads=1')
    connection.execute('SET enable_external_access=false')
    # JSON conversion is in-process; no temporary files or extension downloads.
    columns = ', '.join(f"{key} {kind}" for key, kind in SCHEMA.items())
    connection.execute(f'CREATE TABLE trips ({columns})')
    expressions = ', '.join(f"CAST(value ->> '{key}' AS {kind})" for key, kind in SCHEMA.items())
    connection.execute(f'INSERT INTO trips SELECT {expressions} FROM json_each(?)', [json.dumps(rows)])
    return connection


def validate_rows(rows: list[dict]) -> None:
    if not rows or any(set(r) != set(SCHEMA) for r in rows):
        raise ValueError('Expected nonempty trip rows with the documented schema')
    ids = [r['row_id'] for r in rows]
    if any(type(i) is not str for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Every trip requires a unique string row_id')
    for row in rows:
        if any(type(row[k]) is not (int if t == 'BIGINT' else str) for k,t in SCHEMA.items()):
            raise ValueError('Trip field type does not match schema')
        if not 0 <= row['pickup_hour'] <= 23 or not '2024-01-01' <= row['pickup_date'] < '2024-02-01':
            raise ValueError('Trip time outside January 2024 or valid hour range')
