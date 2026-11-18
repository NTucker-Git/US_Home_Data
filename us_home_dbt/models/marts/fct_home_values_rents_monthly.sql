-- Zillow home values and rents, one row per region per month, with the four
-- measures side by side and 1- and 5-year percent changes.
-- Feeds report sections 1 (home prices) and 2 (rents).

with monthly as (

    select * from {{ ref('stg_zillow__monthly_values') }}

),

-- One row of descriptive fields per region. Zillow's files can disagree on
-- minor fields (e.g. size_rank), so take them from a single row: the mid-tier
-- home value file if the region has it, otherwise rents, latest month first.
regions as (

    select distinct on (region_id)
        region_id,
        geography_level,
        region_name,
        zip_code,
        state_code,
        state_name,
        city,
        metro_name,
        county_name
    from monthly
    order by region_id, (dataset = 'zhvi_mid') desc, month_end_date desc

),

-- Long to wide: one column per measure
pivoted as (

    select
        region_id,
        month_start_date,
        month_end_date,
        max(value) filter (where dataset = 'zhvi_mid') as typical_home_value,
        max(value) filter (where dataset = 'zhvi_bottom') as bottom_tier_home_value,
        max(value) filter (where dataset = 'zhvi_top') as top_tier_home_value,
        max(value) filter (where dataset = 'zori') as typical_rent
    from monthly
    group by region_id, month_start_date, month_end_date

),

-- Percent changes compare with the same region exactly 12 or 60 months
-- earlier. A join on the date (rather than LAG over rows) gives NULL when
-- that month is missing, instead of silently comparing the wrong months.
with_changes as (

    select
        cur.*,
        round(100 * (cur.typical_home_value / yr1.typical_home_value - 1), 2)
            as typical_home_value_change_1y_pct,
        round(100 * (cur.typical_home_value / yr5.typical_home_value - 1), 2)
            as typical_home_value_change_5y_pct,
        round(100 * (cur.typical_rent / yr1.typical_rent - 1), 2)
            as typical_rent_change_1y_pct
    from pivoted as cur
    left join pivoted as yr1
        on yr1.region_id = cur.region_id
        and yr1.month_start_date = cur.month_start_date - interval 12 month
    left join pivoted as yr5
        on yr5.region_id = cur.region_id
        and yr5.month_start_date = cur.month_start_date - interval 60 month

)

select
    r.region_id,
    r.geography_level,
    r.region_name,
    r.zip_code,
    r.state_code,
    r.state_name,
    r.city,
    r.metro_name,
    r.county_name,
    c.month_start_date,
    c.month_end_date,
    c.typical_home_value,
    c.bottom_tier_home_value,
    c.top_tier_home_value,
    c.typical_rent,
    c.typical_home_value_change_1y_pct,
    c.typical_home_value_change_5y_pct,
    c.typical_rent_change_1y_pct
from with_changes as c
inner join regions as r
    on r.region_id = c.region_id
