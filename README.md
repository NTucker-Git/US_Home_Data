# US Home Data Project

A personal analytics pipeline researching US housing trends, built entirely with free tools and using real public data. It pulls data from public APIs and open data sources, stores it in a local DuckDB database, and models it with dbt.

## Status

Work in progress. Currently setting up the project and selecting the first data source.

## Tech stack

- **Python** for extraction and loading
- **DuckDB** as the local analytical database
- **Parquet** for storing staged data
- **dbt-core** (dbt-duckdb) for models, tests, and documentation
- **Power BI Desktop** for visualization
- **Windows Task Scheduler** for daily refreshes

## Project structure

```
raw/        Untouched API responses (not tracked in Git)
staging/    Cleaned Parquet files (not tracked in Git)
logs/       Pipeline run logs (not tracked in Git)
```

## Data sources

_To be added._

## How to run

_To be added._