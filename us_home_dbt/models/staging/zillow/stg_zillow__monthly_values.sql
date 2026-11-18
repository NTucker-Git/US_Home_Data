-- Zillow home values (ZHVI) and rents (ZORI), one row per dataset, region,
-- and month, with geography fields made consistent across file types.

with source as (

    select * from {{ source('zillow', 'monthly_values') }}

),

renamed as (

    select
        dataset,

        -- Zillow files the US row in the metro file, so label it explicitly
        case
            when region_type = 'country' then 'national'
            else geo_level
        end as geography_level,

        region_id,
        region_name,
        case when geo_level = 'zip' then region_name end as zip_code,

        -- State abbreviation: ZIP files have it in State; metro files put the
        -- metro's main state abbreviation in StateName. State files only have
        -- the full name (in region_name).
        case
            when geo_level = 'zip' then state
            when region_type = 'msa' then state_name
        end as state_code,
        case when geo_level = 'state' then region_name end as state_name,

        city,
        case
            when geo_level = 'zip' then metro
            when region_type = 'msa' then region_name
        end as metro_name,
        county_name,
        size_rank,

        -- Zillow dates months by their last day; FRED uses the first day.
        -- Keep both so the sources can be joined.
        month_date as month_end_date,
        cast(date_trunc('month', month_date) as date) as month_start_date,

        value,
        release as source_release

    from source

)

select * from renamed
