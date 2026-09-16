"""Build the committed sample: FIGUREFLOW_TAXI_PARQUET=... python scripts/build_sample.py."""
import json
from pathlib import Path

import duckdb
from figureflow.dataset import CLEAN, file_hash, full_path


def main():
    source = full_path()
    root = Path(__file__).resolve().parents[1]
    output = root / 'data/yellow_tripdata_sample.parquet'
    sql = f"""SELECT * FROM (
    SELECT file_row_number AS source_row_number, * EXCLUDE(file_row_number)
    FROM read_parquet(?, file_row_number=true)
    WHERE {CLEAN}
    ORDER BY md5(CAST(file_row_number AS VARCHAR)), file_row_number
    LIMIT 50000
) ORDER BY source_row_number"""
    with duckdb.connect() as con:
        con.execute('SET threads=1')
        con.execute('CREATE TABLE sample AS ' + sql, [str(source)])
        count = con.execute('SELECT count(*) FROM sample').fetchone()[0]
        if count != 50000:
            raise ValueError(f'Expected 50000 sample rows, found {count}')
        destination = str(output).replace("'", "''")
        con.execute(f"COPY sample TO '{destination}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    manifest = {'source_file': source.name, 'source_sha256': file_hash(source),
                'sample_sha256': file_hash(output), 'rows': count,
                'duckdb_version': duckdb.__version__, 'sampling_sql': sql,
                'row_identity': 'Original zero-based Parquet file_row_number before cleaning',
                'zone_lookup_sha256': file_hash(root / 'data/taxi_zone_lookup.csv')}
    (root / 'data/sample_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Wrote {count} trips to {output}')


if __name__ == '__main__':
    main()
