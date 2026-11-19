-- Zillow home value forecasts (report section 7), one row per region per
-- forecast release, with the 1-, 3-, and 12-month horizons side by side.
-- Every release is kept, so forecasts can later be scored against what
-- actually happened (actual_change_12m_pct fills in once that month's home
-- value is published).

with forecasts as (

    select * from {{ ref('stg_zillow__forecasts') }}
    where dataset = 'zhvf_mid'

),

monthly_values as (

    select region_id, month_end_date, typical_home_value
    from {{ ref('fct_home_values_rents_monthly') }}
    where typical_home_value is not null

),

-- One row per region and base date; horizons become columns
pivoted as (

    select
        region_id,
        base_date,
        any_value(geography_level) as geography_level,
        any_value(region_name) as region_name,
        any_value(zip_code) as zip_code,
        any_value(state_code) as state_code,
        any_value(city) as city,
        any_value(metro_name) as metro_name,
        any_value(county_name) as county_name,
        any_value(source_release) as source_release,
        max(growth_pct) filter (where horizon_months = 1) as forecast_1m_pct,
        max(growth_pct) filter (where horizon_months = 3) as forecast_3m_pct,
        max(growth_pct) filter (where horizon_months = 12) as forecast_12m_pct,
        max(forecast_date) filter (where horizon_months = 12) as forecast_12m_date
    from forecasts
    group by region_id, base_date

)

select
    p.region_id,
    p.geography_level,
    p.region_name,
    p.zip_code,
    p.state_code,
    p.city,
    p.metro_name,
    p.county_name,
    p.base_date,
    p.source_release,
    p.forecast_1m_pct,
    p.forecast_3m_pct,
    p.forecast_12m_pct,
    p.forecast_12m_date,
    base.typical_home_value as base_home_value,
    -- The 12-month forecast expressed in dollars
    round(base.typical_home_value * (1 + p.forecast_12m_pct / 100), 0) as forecast_12m_home_value,
    -- What actually happened, once the target month is published
    actual.typical_home_value as actual_12m_home_value,
    round(100 * (actual.typical_home_value / base.typical_home_value - 1), 2) as actual_change_12m_pct
from pivoted as p
left join monthly_values as base
    on base.region_id = p.region_id
    and base.month_end_date = p.base_date
left join monthly_values as actual
    on actual.region_id = p.region_id
    and actual.month_end_date = p.forecast_12m_date
