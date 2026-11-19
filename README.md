# US Home Data Project

A personal analytics pipeline researching US housing trends, built entirely with free tools and using real public data. It pulls data from public APIs and open data sources, stores it in a local DuckDB database, and models it with dbt.

## Status

Work in progress. Two sources are loaded into DuckDB and exported to Parquet:

- **FRED**: 44 national housing series (mortgage rates by loan type, home prices, listings, sales, the construction pipeline, rents, vacancy, affordability, and credit risk), extracted from the API.
- **Zillow Research**: home values, rents, and one-year home value forecasts for the US, 51 states, about 900 metros, and about 28,000 ZIP codes (about 7.9 million rows).

A dbt project ([us_home_dbt](us_home_dbt/)) turns the raw tables into tested staging views and marts:

- Monthly and current home values and rents for every region, with 1- and 5-year changes (report sections 1 and 2).
- Mortgage rates by loan type, with weekly and yearly changes, the 52-week range, and the spread over the 10-year Treasury (report section 3).
- Affordability for every region: the monthly principal-and-interest payment on the typical home at today's 30-year rate with 20% down, the same payment a year earlier, the price-to-rent ratio, and nationally the payment as a share of median household income (report section 4).
- Zillow's 1-, 3-, and 12-month home value forecasts for the US, metros, and ZIP codes, with every release kept so forecasts can later be scored against actual outcomes (report section 7).

`dbt build` runs 10 models, 2 seeds (mortgage rate labels; state FIPS codes, abbreviations, and names from the Census Bureau), and 90 data tests.

The report this pipeline will feed is defined in the [report specification](docs/report_spec.md).

Next up:

- Marts for a national market panel and ZIP comparisons (the rest of report v1)
- A first version of the "pick a ZIP, get a report" output
- Schedule daily refreshes with Windows Task Scheduler

## Tech stack

- **Python** (`requests`, `python-dotenv`) for extraction and loading
- **DuckDB** as the local analytical database
- **Parquet** for storing staged data
- **dbt-core** (dbt-duckdb, dbt_utils) for models, tests, and documentation
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

Zillow Research ──> manual download ──> raw/zillow/<YYYY-MM>/*.csv       (original files, one folder per monthly release)
                                                │
                                                v
                        load/load_zillow.py ──> us_home_data.duckdb       (raw_zillow.monthly_values, raw_zillow.forecasts)
                                                │
                                                v
                                         staging/zillow/*.parquet

us_home_data.duckdb  raw_fred, raw_zillow  (sources, tested)
        │
        v   dbt build (us_home_dbt/)
    staging   stg_fred__observations, stg_zillow__monthly_values, stg_zillow__forecasts   (views)
        │
        v
    marts     fct_home_values_rents_monthly, home_values_rents_current,                    (tables)
              fct_mortgage_rates, mortgage_rates_current, affordability_current,
              fct_home_value_forecasts, home_value_forecast_current
```

- **Raw data is saved untouched** with dated file or folder names, so any load can be rerun or audited against the original data.
- **Loads are idempotent.** The load scripts upsert with a parameterized `MERGE` on their natural keys (series and date for FRED; dataset, region, and month for Zillow): existing rows are updated, new rows are inserted, and nothing is duplicated on a rerun. This picks up revisions to past values (Zillow restates its full history when its methodology changes) and keeps history for series where FRED only publishes the most recent months.
- **Wide files are reshaped to long.** Zillow publishes one column per month; the load uses DuckDB's `UNPIVOT` to produce one row per region per month. Zillow forecasts are kept for every monthly release, so they can later be compared with actual outcomes.
- **Identifiers keep their format.** Zillow files are read as text first, so ZIP codes such as `01001` keep their leading zeros.
- **Missing values are handled explicitly.** FRED marks missing observations with `"."`, which the load converts to `NULL` with `TRY_CAST`; empty Zillow cells are dropped.
- **Errors stop the run.** HTTP errors, missing inputs, unrecognized file names, and unexpected file layouts end the script with an error, so later steps never run on bad data.
- **Every layer is tested.** dbt tests check the raw sources and each model: no missing keys, no duplicate keys (series and date, or dataset, region, and month), allowed values, 5-digit ZIP codes, and bottom-tier ≤ typical ≤ top-tier home values.
- **Rates are matched to the right Treasury yield.** Weekly mortgage rates and daily Treasury yields aren't published on the same days, so an `ASOF JOIN` pairs each rate with the latest yield on or before its date, and a test checks the match is never more than a week old.
- **Percent changes compare exact dates.** 1- and 5-year changes join each month to the same month 12 or 60 months earlier, so a gap in the data leaves the change empty instead of comparing the wrong months.
- **Source terms are respected.** Zillow's Terms of Use prohibit automated access to its services, so Zillow files are downloaded by hand each month and only the load is scripted.

## Project structure

```
extract/    One extract script per source (extract_fred.py)
load/       One load script per source (load_fred.py, load_zillow.py)
us_home_dbt/  dbt project: sources, staging models, marts, tests
docs/       Report specification
raw/        Untouched API responses and downloaded files (not tracked in Git)
staging/    Parquet exports (not tracked in Git)
logs/       Pipeline run logs (not tracked in Git)
```

The DuckDB database (`us_home_data.duckdb`) and the `.env` file holding API keys are also not tracked in Git.

## Data sources

| Source | Data | Access | Status |
|---|---|---|---|
| [FRED](https://fred.stlouisfed.org/) | 44 national series: 30- and 15-year mortgage rates; FHA, VA, USDA, jumbo, and conforming rate indexes; 10-year Treasury; Case-Shiller and FHFA price indexes; Realtor.com listings (prices, price per sq ft, home size, inventory, days on market, price cuts); new and existing home sales; the construction pipeline from permits to completions; rent, shelter, and owners' equivalent rent CPI; vacancy and homeownership rates; median household income; mortgage debt service and delinquency; unemployment; population | API, free key | Loaded |
| [FHFA](https://www.fhfa.gov/data/hpi) | House Price Index (national to ZIP level) | File download | Planned |
| [Zillow Research](https://www.zillow.com/research/data/) | Home values (ZHVI: typical, bottom-tier, and top-tier homes), rents (ZORI), and one-year home value forecasts (ZHVF), for the US, states, metros, and ZIP codes | CSV, downloaded manually each month | Loaded (bottom and top tiers for the US, states, and metros; Zillow doesn't publish them by ZIP) |
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

4. For Zillow, download these files from [Zillow Research](https://www.zillow.com/research/data/) into a folder named for the release month (for example `raw\zillow\2026-11\`), keeping the original file names:

   | Data | Geographies | File name suffix |
   |---|---|---|
   | Home values (ZHVI), typical | Metro & U.S., State, ZIP Code | `_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv` |
   | Home values, bottom and top tier | Metro & U.S., State | `_zhvi_uc_sfrcondo_tier_0.0_0.33_sm_sa_month.csv`, `_zhvi_uc_sfrcondo_tier_0.67_1.0_sm_sa_month.csv` |
   | Rents (ZORI) | Metro & U.S., ZIP Code | `_zori_uc_sfrcondomfr_sm_month.csv` |
   | Home value forecasts (ZHVF) | Metro & U.S., ZIP Code | `_zhvf_growth_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv` |

   Then run:

   ```powershell
   python load/load_zillow.py
   ```

   The script loads the newest release folder and prints row counts, date ranges, and a duplicate-key check.

5. Build and test the dbt models (run dbt from inside the project folder, where `profiles.yml` lives):

   ```powershell
   cd us_home_dbt
   dbt deps     # install dbt_utils
   dbt build    # build the models and run the tests
   dbt docs generate
   dbt docs serve   # browse model docs and the lineage graph at http://localhost:8080
   ```

## Attribution

- Data from FRED, Federal Reserve Bank of St. Louis.
- Data Provided by Zillow Group.

This project is not endorsed by or affiliated with any data provider.
