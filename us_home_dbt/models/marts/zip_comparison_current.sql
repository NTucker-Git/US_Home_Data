-- "How does this ZIP compare?": each ZIP code's latest numbers next to its
-- state and the US, with its rank and percentile within the state.
-- Zillow publishes no state-level rents or forecasts, so for those the state
-- comparison is the median across the state's ZIP codes (state_zip_median_*).

with affordability as (

    select * from {{ ref('affordability_current') }}

),

values_rents as (

    select * from {{ ref('home_values_rents_current') }}

),

forecasts as (

    select * from {{ ref('home_value_forecast_current') }}

),

states as (

    select * from {{ ref('states') }}

),

-- Latest figures for every region that has a home value
regions as (

    select
        a.region_id,
        a.geography_level,
        a.region_name,
        a.zip_code,
        a.city,
        a.county_name,
        a.metro_name,
        a.state_code,
        a.home_value_as_of,
        a.typical_home_value,
        v.typical_home_value_change_1y_pct,
        v.typical_home_value_change_5y_pct,
        a.typical_rent,
        v.typical_rent_change_1y_pct,
        a.price_to_rent_ratio,
        a.monthly_payment,
        f.forecast_12m_pct
    from affordability as a
    inner join values_rents as v
        on v.region_id = a.region_id
    left join forecasts as f
        on f.region_id = a.region_id

),

zips as (

    select
        r.*,
        s.state_fips,
        s.state_name
    from regions as r
    inner join states as s
        on s.state_code = r.state_code
    where r.geography_level = 'zip'

),

state_level as (

    select
        s.state_code,
        r.typical_home_value as state_home_value,
        r.typical_home_value_change_1y_pct as state_home_value_change_1y_pct,
        r.typical_home_value_change_5y_pct as state_home_value_change_5y_pct,
        r.monthly_payment as state_monthly_payment
    from regions as r
    inner join states as s
        on s.state_name = r.region_name
    where r.geography_level = 'state'

),

-- Medians across each state's ZIPs, for measures Zillow doesn't publish by state
state_zip_medians as (

    select
        state_code,
        round(median(typical_rent), 0) as state_zip_median_rent,
        round(median(price_to_rent_ratio), 1) as state_zip_median_price_to_rent_ratio,
        round(median(forecast_12m_pct), 2) as state_zip_median_forecast_12m_pct
    from zips
    group by state_code

),

us as (

    select
        typical_home_value as us_home_value,
        typical_home_value_change_1y_pct as us_home_value_change_1y_pct,
        typical_home_value_change_5y_pct as us_home_value_change_5y_pct,
        typical_rent as us_rent,
        typical_rent_change_1y_pct as us_rent_change_1y_pct,
        price_to_rent_ratio as us_price_to_rent_ratio,
        monthly_payment as us_monthly_payment,
        forecast_12m_pct as us_forecast_12m_pct
    from regions
    where geography_level = 'national'

),

ranked as (

    select
        z.*,
        count(*) over (partition by z.state_code) as zips_in_state,
        -- 1 = highest home value in the state
        rank() over (partition by z.state_code order by z.typical_home_value desc) as home_value_rank_in_state,
        -- Percent of the state's ZIPs with a lower home value (0-100)
        round(100 * percent_rank() over (partition by z.state_code order by z.typical_home_value), 0)
            as home_value_percentile_in_state,
        round(100 * percent_rank() over (order by z.typical_home_value), 0)
            as home_value_percentile_in_us,
        -- 1 = fastest-rising home value in the state; ZIPs without a 1-year
        -- change are ranked separately (partitioned out) and then set to NULL
        case
            when z.typical_home_value_change_1y_pct is not null
                then rank() over (
                    partition by z.state_code, z.typical_home_value_change_1y_pct is null
                    order by z.typical_home_value_change_1y_pct desc
                )
        end as home_value_change_1y_rank_in_state,
        count(z.typical_home_value_change_1y_pct) over (partition by z.state_code)
            as zips_in_state_with_change_1y
    from zips as z

)

select
    r.region_id,
    r.zip_code,
    r.city,
    r.county_name,
    r.metro_name,
    r.state_code,
    r.state_name,
    r.state_fips,
    r.home_value_as_of,

    -- Home value: ZIP, state, US
    r.typical_home_value,
    st.state_home_value,
    us.us_home_value,
    round(100 * (r.typical_home_value / st.state_home_value - 1), 1) as home_value_vs_state_pct,
    round(100 * (r.typical_home_value / us.us_home_value - 1), 1) as home_value_vs_us_pct,
    r.home_value_rank_in_state,
    r.zips_in_state,
    r.home_value_percentile_in_state,
    r.home_value_percentile_in_us,

    -- Home value change
    r.typical_home_value_change_1y_pct,
    st.state_home_value_change_1y_pct,
    us.us_home_value_change_1y_pct,
    r.home_value_change_1y_rank_in_state,
    r.zips_in_state_with_change_1y,
    r.typical_home_value_change_5y_pct,
    st.state_home_value_change_5y_pct,
    us.us_home_value_change_5y_pct,

    -- Monthly payment (principal and interest, 20% down)
    r.monthly_payment,
    st.state_monthly_payment,
    us.us_monthly_payment,

    -- Rent and price-to-rent (state = median across the state's ZIPs)
    r.typical_rent,
    m.state_zip_median_rent,
    us.us_rent,
    r.typical_rent_change_1y_pct,
    us.us_rent_change_1y_pct,
    r.price_to_rent_ratio,
    m.state_zip_median_price_to_rent_ratio,
    us.us_price_to_rent_ratio,

    -- Zillow 12-month forecast (state = median across the state's ZIPs)
    r.forecast_12m_pct,
    m.state_zip_median_forecast_12m_pct,
    us.us_forecast_12m_pct

from ranked as r
left join state_level as st
    on st.state_code = r.state_code
left join state_zip_medians as m
    on m.state_code = r.state_code
cross join us
