-- One row per FRED series per observation date, without empty observations.

with source as (

    select * from {{ source('fred', 'observations') }}

)

select
    series_id,
    observation_date,
    value

from source
-- FRED reports some dates with no value (e.g. bond-market holidays for DGS10);
-- they carry no information, so they are dropped here.
where value is not null
