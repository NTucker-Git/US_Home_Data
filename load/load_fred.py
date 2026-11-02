import sys
from pathlib import Path

import duckdb

# DuckDB draws tables with box characters that Windows' default encoding can't
# print when output goes to a file (as it will in scheduled runs), so force UTF-8
sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "raw" / "fred"

# Find the most recent raw file for each series. Filenames look like
# <SERIES_ID>_<YYYY-MM-DD>.json, so sorting by name puts the newest last.
latest_files = {}
for f in sorted(RAW_DIR.glob("*_*.json")):
    series_id = f.stem.rsplit("_", 1)[0]
    latest_files[series_id] = f
if not latest_files:
    raise SystemExit(f"No raw files found in {RAW_DIR}. Run the extract script first.")

con = duckdb.connect(str(PROJECT_ROOT / "us_home_data.duckdb"))

con.execute("CREATE SCHEMA IF NOT EXISTS raw_fred")
con.execute("""
    CREATE TABLE IF NOT EXISTS raw_fred.observations (
        series_id        VARCHAR,
        observation_date DATE,
        value            DOUBLE,
        loaded_at        TIMESTAMP DEFAULT current_timestamp
    )
""")

# MERGE is an upsert: update rows that already exist, insert new ones, and leave
# rows that aren't in the new file alone. That makes re-runs safe, picks up FRED's
# revisions, and keeps history for series where FRED only serves recent months.
# The ? placeholders are filled in by DuckDB, not pasted into the SQL text.
merge_sql = """
    MERGE INTO raw_fred.observations AS t
    USING (
        SELECT ? AS series_id
            , CAST(o.date AS DATE) AS observation_date
            , TRY_CAST(o.value AS DOUBLE) AS value  -- FRED uses "." for missing values
        FROM (
            SELECT unnest(observations) AS o
            FROM read_json_auto(?)
            )
    ) AS s
    ON t.series_id = s.series_id AND t.observation_date = s.observation_date
    WHEN MATCHED THEN UPDATE SET value = s.value, loaded_at = current_timestamp
    WHEN NOT MATCHED THEN INSERT (series_id, observation_date, value, loaded_at)
        VALUES (s.series_id, s.observation_date, s.value, current_timestamp)
"""

for series_id, path in latest_files.items():
    con.execute(merge_sql, [series_id, path.as_posix()])
    print(f"Loaded {series_id} from {path.name}")

# Export to Parquet
out_dir = PROJECT_ROOT / "staging" / "fred"
out_dir.mkdir(parents=True, exist_ok=True)
parquet_path = (out_dir / "observations.parquet").as_posix()
con.execute(f"""
    COPY (
        SELECT series_id, observation_date, value
        FROM raw_fred.observations
        ORDER BY series_id, observation_date
    ) TO '{parquet_path}' (FORMAT parquet)
""")

# Quick check: one row per series
con.sql(
"   SELECT series_id" \
"       , count(*) AS row_count" \
"       , count(value) AS non_null" \
"       , min(observation_date) AS first_date" \
"       , max(observation_date) AS last_date" \
"   FROM raw_fred.observations" \
"   GROUP BY series_id" \
"   ORDER BY series_id"
).show(max_rows=100)

con.close()
