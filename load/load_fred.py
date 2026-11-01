from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERIES_ID = "MORTGAGE30US"

# Find the most recent raw file for this series (filenames end in the date)
files = sorted((PROJECT_ROOT / "raw" / "fred").glob(f"{SERIES_ID}_*.json"))
if not files:
    raise SystemExit(f"No raw files found for {SERIES_ID}. Run the extract script first.")
latest = files[-1].as_posix()

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

# Delete-then-insert makes the script safe to re-run
con.execute(f"DELETE FROM raw_fred.observations WHERE series_id = '{SERIES_ID}'")
con.execute(f"""
    INSERT INTO raw_fred.observations (series_id, observation_date, value)
    SELECT '{SERIES_ID}'
        , CAST(o.date AS DATE)
        , TRY_CAST(o.value AS DOUBLE)
    FROM (
        SELECT unnest(observations) AS o 
        FROM read_json_auto('{latest}')
        )
""")

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

# Quick check
con.sql(
"   SELECT count(*) AS row_count" \
"       , min(observation_date) AS first_date" \
"       , max(observation_date) AS last_date" \
"   FROM raw_fred.observations"
).show()

con.sql(
"   SELECT * " \
"   FROM raw_fred.observations" \
"   ORDER BY observation_date DESC" \
"   LIMIT 5"
).show()

con.close()