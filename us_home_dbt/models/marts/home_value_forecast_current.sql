-- Latest Zillow home value forecast per region: the headline numbers for
-- report section 7 (outlook).

select
    region_id,
    geography_level,
    region_name,
    zip_code,
    state_code,
    city,
    metro_name,
    county_name,
    base_date,
    source_release,
    forecast_1m_pct,
    forecast_3m_pct,
    forecast_12m_pct,
    forecast_12m_date,
    base_home_value,
    forecast_12m_home_value
from {{ ref('fct_home_value_forecasts') }}
qualify row_number() over (partition by region_id order by base_date desc) = 1
