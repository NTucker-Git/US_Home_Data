-- Zillow home value forecasts (ZHVF), one row per dataset, region, base date,
-- and forecast date, with the same geography fields as the monthly values.

with source as (

    select * from {{ source('zillow', 'forecasts') }}

),

renamed as (

    select
        dataset,

        case
            when region_type = 'country' then 'national'
            else geo_level
        end as geography_level,

        region_id,
        region_name,
        case when geo_level = 'zip' then region_name end as zip_code,
        case
            when geo_level = 'zip' then state
            when region_type = 'msa' then state_name
        end as state_code,
        city,
        case
            when geo_level = 'zip' then metro
            when region_type = 'msa' then region_name
        end as metro_name,
        county_name,
        size_rank,

        base_date,
        forecast_date,
        -- Months ahead of the base date: 1 (next month), 3 (quarter), 12 (year)
        cast(datediff('month', base_date, forecast_date) as integer) as horizon_months,

        -- Percent growth from base_date to forecast_date (0.9 means +0.9%)
        growth_pct,
        release as source_release

    from source

)

select * from renamed
