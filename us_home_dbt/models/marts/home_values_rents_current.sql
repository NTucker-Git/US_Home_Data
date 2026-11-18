-- Latest home value and rent figures for each region: the headline numbers
-- for report sections 1 (home prices) and 2 (rents).

with monthly as (

    select * from {{ ref('fct_home_values_rents_monthly') }}

),

-- Each measure's latest available month per region. They can differ (e.g. a
-- ZIP whose rent data stopped earlier), so each gets its own "as of" month.
latest_home_value as (

    select
        region_id,
        month_end_date as home_value_as_of,
        typical_home_value,
        bottom_tier_home_value,
        top_tier_home_value,
        typical_home_value_change_1y_pct,
        typical_home_value_change_5y_pct
    from monthly
    where typical_home_value is not null
    qualify row_number() over (partition by region_id order by month_end_date desc) = 1

),

latest_rent as (

    select
        region_id,
        month_end_date as rent_as_of,
        typical_rent,
        typical_rent_change_1y_pct
    from monthly
    where typical_rent is not null
    qualify row_number() over (partition by region_id order by month_end_date desc) = 1

),

regions as (

    select distinct
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

)

select
    r.*,
    hv.home_value_as_of,
    hv.typical_home_value,
    hv.bottom_tier_home_value,
    hv.top_tier_home_value,
    hv.typical_home_value_change_1y_pct,
    hv.typical_home_value_change_5y_pct,
    rt.rent_as_of,
    rt.typical_rent,
    rt.typical_rent_change_1y_pct
from regions as r
left join latest_home_value as hv
    on hv.region_id = r.region_id
left join latest_rent as rt
    on rt.region_id = r.region_id
