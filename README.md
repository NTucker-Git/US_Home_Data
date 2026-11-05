# US Home Data Project

A personal analytics pipeline researching US housing trends, built entirely with free tools and using real public data. It pulls data from public APIs and open data sources, stores it in a local DuckDB database, and models it with dbt.

## Status

Work in progress. The first source is working end to end: 43 national housing series from FRED (mortgage rates by loan type, home prices, listings, sales, the construction pipeline, rents, vacancy, affordability, and credit risk) are extracted from the API, loaded into DuckDB, and exported to Parquet.

The report this pipeline will feed is defined in the [report specification](docs/report_spec.md).

Next up:

- Add Zillow home values, rents, and forecasts at national, state, and ZIP code level
- Set up dbt staging models, tests, and documentation
- Schedule daily refreshes with Windows Task Scheduler

## Tech stack

- **Python** (`requests`, `python-dotenv`) for extraction and loading
- **DuckDB** as the local analytical database
- **Parquet** for storing staged data
- **dbt-core** (dbt-duckdb) for models, tests, and documentation (planned)
- **Power BI Desktop** for visualization (planned)
- **Windows Task Scheduler** for daily refreshes (planned)

## How it works

```
FRED API ──> extract/extract_fred.py ──> raw/fred/<series>_<date>.json   (untouched response)
                                                │
                                                v
                          load/load_fred.py ──> us_home_data.duckdb       (raw_fred.observations)
                                                │
                                                v
                                         staging/fred/observations.parquet
```

- **Raw responses are saved untouched** with dated filenames, so any load can be rerun or audited against the original data.
- **Loads are idempotent.** The load script upserts with a parameterized `MERGE` on series and date: existing rows are updated, new rows are inserted, and nothing is duplicated on a rerun. This picks up revisions FRED makes to past values, and keeps history for series where FRED only publishes the most recent months.
- **Missing values are handled explicitly.** FRED marks missing observations with `"."`, which the load converts to `NULL` with `TRY_CAST`.
- **Errors stop the run.** HTTP errors and missing inputs end the script with an error, so later steps never run on bad data.

## Project structure

```
extract/    One extract script per source (extract_fred.py)
load/       One load script per source (load_fred.py)
raw/        Untouched API responses (not tracked in Git)
staging/    Parquet exports (not tracked in Git)
logs/       Pipeline run logs (not tracked in Git)
```

The DuckDB database (`us_home_data.duckdb`) and the `.env` file holding API keys are also not tracked in Git.

## Data sources

| Source | Data | Access | Status |
|---|---|---|---|
| [FRED](https://fred.stlouisfed.org/) | 43 national series: 30- and 15-year mortgage rates; FHA, VA, USDA, jumbo, and conforming rate indexes; 10-year Treasury; Case-Shiller and FHFA price indexes; Realtor.com listings (prices, price per sq ft, home size, inventory, days on market, price cuts); new and existing home sales; the construction pipeline from permits to completions; rent, shelter, and owners' equivalent rent CPI; vacancy and homeownership rates; median household income; mortgage debt service and delinquency; unemployment; population | API, free key | Loaded |
| [FHFA](https://www.fhfa.gov/data/hpi) | House Price Index (national to ZIP level) | File download | Planned |
| [Zillow Research](https://www.zillow.com/research/data/) | Home values (ZHVI), rents (ZORI), inventory | CSV download | Planned |
| [Redfin Data Center](https://www.redfin.com/news/data-center/) | Market tracker, price drops, sales metrics | CSV download | Planned |
| [U.S. Census Bureau](https://www.census.gov/data/developers.html) | ACS home values, rents, occupancy; building permits | API, free key | Planned |
| [HUD USER](https://www.huduser.gov/portal/datasets/fmr.html) | Fair Market Rents, income limits | API, free token | Planned |

## How to run

Requires Windows, Python 3, and a free [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html).

1. Clone the repo and create a virtual environment:

   ```powershell
   git clone https://github.com/NTucker-Git/US_Home_Data.git
   cd US_Home_Data
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root with your key:

   ```
   FRED_API_KEY=your_key_here
   ```

3. Run the extract, then the load:

   ```powershell
   python extract/extract_fred.py
   python load/load_fred.py
   ```

   The load script prints the row count and date range for each series when it finishes.

## Attribution

Data from FRED, Federal Reserve Bank of St. Louis. This project is not endorsed by or affiliated with any data provider.
