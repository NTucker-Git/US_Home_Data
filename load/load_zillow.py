"""Load manually downloaded Zillow Research CSVs into DuckDB.

Zillow's Terms of Use ban automated access to its services, so there is no
extract script for Zillow. Each month (after Zillow's release around the 16th)
the CSVs are downloaded by hand into raw/zillow/<YYYY-MM>/ with their original
file names. This script loads the newest of those folders.

Zillow files are "wide": one row per region and one column per month. This
script unpivots them to "long" (one row per region per month) and upserts into:
  raw_zillow.monthly_values  ZHVI home values (3 tiers) and ZORI rents
  raw_zillow.forecasts       ZHVF home value forecasts (% growth)
"""

import io
import re
import sys
from pathlib import Path

import duckdb

# DuckDB draws tables with box characters that Windows' default encoding can't
# print when output goes to a file (as it will in scheduled runs), so force UTF-8.
# The isinstance check tells the type checker (Pylance) that reconfigure exists.
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "raw" / "zillow"

# Every file name is <Geo>_<suffix>.csv. The suffix says which dataset it is.
# Unknown files stop the script (fail loudly) instead of being silently skipped.
DATASETS = {
    "zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month": ("monthly_values", "zhvi_mid"),
    "zhvi_uc_sfrcondo_tier_0.0_0.33_sm_sa_month": ("monthly_values", "zhvi_bottom"),
    "zhvi_uc_sfrcondo_tier_0.67_1.0_sm_sa_month": ("monthly_values", "zhvi_top"),
    "zori_uc_sfrcondomfr_sm_month": ("monthly_values", "zori"),
    "zhvf_growth_uc_sfrcondo_tier_0.33_0.67_sm_sa_month": ("forecasts", "zhvf_mid"),
}
GEO_LEVELS = {"State": "state", "Metro": "metro", "County": "county", "City": "city", "Zip": "zip"}

REQUIRED_COLS = ["RegionID", "SizeRank", "RegionName", "RegionType"]
# Only some geographies have these columns (State and Metro files lack most of them)
OPTIONAL_COLS = {
    "StateName": "state_name",
    "State": "state",
    "City": "city",
    "Metro": "metro",
    "CountyName": "county_name",
}
DATE_COL = re.compile(r"\d{4}-\d{2}-\d{2}")

# Column layout of each table. "keys" identify a row for the MERGE.
TABLES = {
    "monthly_values": {
        "keys": ["dataset", "region_id", "month_date"],
        "date_col": "month_date",
        "value_col": "value",
    },
    "forecasts": {
        "keys": ["dataset", "region_id", "base_date", "forecast_date"],
        "date_col": "forecast_date",
        "value_col": "growth_pct",
    },
}
COMMON_COLS = ["dataset", "geo_level", "region_id", "region_type", "region_name",
               *OPTIONAL_COLS.values(), "size_rank"]


def table_columns(table):
    """All columns of a table except loaded_at, in table order."""
    extra = ["base_date"] if table == "forecasts" else []
    t = TABLES[table]
    return COMMON_COLS + extra + [t["date_col"], t["value_col"], "release", "source_file"]


def scalar(con, sql):
    """Run a query that returns a single value, such as count(*)."""
    row = con.execute(sql).fetchone()
    if row is None:
        raise RuntimeError(f"Query returned no rows: {sql}")
    return row[0]


# --- Find the newest release folder -----------------------------------------
release_dirs = sorted(
    p for p in RAW_DIR.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}", p.name)
) if RAW_DIR.exists() else []
if not release_dirs:
    raise SystemExit(f"No release folders like 2026-11 found in {RAW_DIR}. Download the Zillow CSVs first.")
release_dir = release_dirs[-1]
release = release_dir.name

files = sorted(release_dir.glob("*.csv"))
if not files:
    raise SystemExit(f"No CSV files in {release_dir}.")

# Check every file name before loading anything
plan = []
for path in files:
    geo, _, suffix = path.stem.partition("_")
    if geo not in GEO_LEVELS or suffix not in DATASETS:
        raise SystemExit(f"Unrecognized Zillow file: {path.name}. Add it to DATASETS/GEO_LEVELS if it's wanted.")
    table, dataset = DATASETS[suffix]
    plan.append((path, GEO_LEVELS[geo], table, dataset))

con = duckdb.connect(str(PROJECT_ROOT / "us_home_data.duckdb"))
con.execute("CREATE SCHEMA IF NOT EXISTS raw_zillow")

optional_ddl = ", ".join(f"{c} VARCHAR" for c in OPTIONAL_COLS.values())
con.execute(f"""
    CREATE TABLE IF NOT EXISTS raw_zillow.monthly_values (
        dataset VARCHAR, geo_level VARCHAR, region_id INTEGER, region_type VARCHAR,
        region_name VARCHAR, {optional_ddl}, size_rank INTEGER,
        month_date DATE, value DOUBLE,
        release VARCHAR, source_file VARCHAR,
        loaded_at TIMESTAMP DEFAULT current_timestamp
    )
""")
con.execute(f"""
    CREATE TABLE IF NOT EXISTS raw_zillow.forecasts (
        dataset VARCHAR, geo_level VARCHAR, region_id INTEGER, region_type VARCHAR,
        region_name VARCHAR, {optional_ddl}, size_rank INTEGER,
        base_date DATE, forecast_date DATE, growth_pct DOUBLE,
        release VARCHAR, source_file VARCHAR,
        loaded_at TIMESTAMP DEFAULT current_timestamp
    )
""")

# --- Load each file ---------------------------------------------------------
for path, geo_level, table, dataset in plan:
    # Read everything as text first (all_varchar). This keeps ZIP codes like
    # 01001 intact and avoids type clashes between months; values are cast below.
    read_sql = "read_csv(?, header = true, all_varchar = true)"
    cols = [d[0] for d in con.execute(f"SELECT * FROM {read_sql} LIMIT 0", [path.as_posix()]).description]

    missing = [c for c in REQUIRED_COLS if c not in cols]
    date_cols = [c for c in cols if DATE_COL.fullmatch(c)]
    if missing or not date_cols:
        raise SystemExit(f"{path.name}: unexpected layout (missing {missing or 'date columns'}). Zillow may have changed the file.")
    if table == "forecasts" and "BaseDate" not in cols:
        raise SystemExit(f"{path.name}: forecast file without a BaseDate column.")

    # Column names below come from our own lists or match the date pattern,
    # so it's safe to put them in the SQL text. Values still use ? parameters.
    optional_select = ", ".join(
        f'"{src}" AS {dst}' if src in cols else f"CAST(NULL AS VARCHAR) AS {dst}"
        for src, dst in OPTIONAL_COLS.items()
    )
    unpivot_on = ", ".join(f'"{c}"' for c in date_cols)
    t = TABLES[table]
    base_date_select = "CAST(BaseDate AS DATE) AS base_date," if table == "forecasts" else ""

    # UNPIVOT turns the month columns into rows; empty cells are dropped.
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE stg AS
        SELECT CAST(? AS VARCHAR) AS dataset
            , CAST(? AS VARCHAR) AS geo_level
            , CAST(RegionID AS INTEGER) AS region_id
            , RegionType AS region_type
            , RegionName AS region_name
            , {optional_select}
            , CAST(SizeRank AS INTEGER) AS size_rank
            , {base_date_select}
              CAST(period AS DATE) AS {t["date_col"]}
            , TRY_CAST(raw_value AS DOUBLE) AS {t["value_col"]}
            , CAST(? AS VARCHAR) AS release
            , CAST(? AS VARCHAR) AS source_file
        FROM (
            UNPIVOT (SELECT * FROM {read_sql})
            ON {unpivot_on}
            INTO NAME period VALUE raw_value
        )
    """, [dataset, geo_level, release, path.name, path.as_posix()])

    # MERGE is an upsert: Zillow restates history, so matching rows are updated,
    # new rows are inserted, and rows missing from the new file are left alone.
    all_cols = table_columns(table)
    update_cols = [c for c in all_cols if c not in t["keys"]]
    con.execute(f"""
        MERGE INTO raw_zillow.{table} AS t
        USING stg AS s
        ON {" AND ".join(f"t.{k} = s.{k}" for k in t["keys"])}
        WHEN MATCHED THEN UPDATE SET {", ".join(f"{c} = s.{c}" for c in update_cols)}, loaded_at = current_timestamp
        WHEN NOT MATCHED THEN INSERT ({", ".join(all_cols)}, loaded_at)
            VALUES ({", ".join(f"s.{c}" for c in all_cols)}, current_timestamp)
    """)
    n = scalar(con, "SELECT count(*) FROM stg")
    print(f"Loaded {n:>9,} rows  {dataset:<12} {geo_level:<6} from {release}/{path.name}")

# --- Export to Parquet ------------------------------------------------------
out_dir = PROJECT_ROOT / "staging" / "zillow"
out_dir.mkdir(parents=True, exist_ok=True)
for table, t in TABLES.items():
    parquet_path = (out_dir / f"{table}.parquet").as_posix()
    order_by = ", ".join(["dataset", "geo_level", *t["keys"][1:]])
    con.execute(f"""
        COPY (SELECT * EXCLUDE (loaded_at) FROM raw_zillow.{table} ORDER BY {order_by})
        TO '{parquet_path}' (FORMAT parquet)
    """)

# --- Quick checks -----------------------------------------------------------
print("\nmonthly_values:")
con.sql("""
    SELECT dataset, geo_level
        , count(DISTINCT region_id) AS regions
        , count(*) AS row_count
        , min(month_date) AS first_month
        , max(month_date) AS last_month
    FROM raw_zillow.monthly_values
    GROUP BY ALL ORDER BY ALL
""").show()

print("forecasts:")
con.sql("""
    SELECT dataset, geo_level, base_date
        , count(DISTINCT region_id) AS regions
        , count(*) AS row_count
        , min(forecast_date) AS first_target
        , max(forecast_date) AS last_target
    FROM raw_zillow.forecasts
    GROUP BY ALL ORDER BY ALL
""").show()

print("Duplicate keys (should all be 0):")
for table, t in TABLES.items():
    keys = ", ".join(t["keys"])
    dupes = scalar(con, f"""
        SELECT count(*) FROM (
            SELECT {keys} FROM raw_zillow.{table} GROUP BY {keys} HAVING count(*) > 1
        )
    """)
    print(f"  {table}: {dupes}")

con.close()
