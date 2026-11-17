# us_home_dbt

The dbt project for US Home Data. It transforms the raw tables loaded by the Python scripts in `load/` into tested, documented models in the same DuckDB database (`../us_home_data.duckdb`).

Run dbt commands from this folder, so dbt finds `profiles.yml`:

```powershell
cd us_home_dbt
dbt debug    # check the connection
dbt build    # run models and tests
```

See the [main README](../README.md) for the full pipeline.
