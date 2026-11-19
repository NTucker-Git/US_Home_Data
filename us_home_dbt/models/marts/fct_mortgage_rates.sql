-- Every mortgage rate observation for report section 3, with the 10-year
-- Treasury yield on the same date and the spread between them.

with observations as (

    select * from {{ ref('stg_fred__observations') }}

),

series as (

    select * from {{ ref('mortgage_rate_series') }}

),

rates as (

    select
        o.series_id,
        o.observation_date as rate_date,
        o.value as rate_pct
    from observations as o
    inner join series as s
        on s.series_id = o.series_id

),

treasury as (

    select
        observation_date as treasury_date,
        value as treasury_10y_pct
    from observations
    where series_id = 'DGS10'

)

select
    s.series_id,
    s.rate_name,
    s.rate_source,
    s.loan_type,
    s.term_years,
    s.frequency,
    s.display_order,
    r.rate_date,
    r.rate_pct,
    t.treasury_date,
    t.treasury_10y_pct,
    round(r.rate_pct - t.treasury_10y_pct, 3) as spread_to_treasury_pct_pts
from rates as r
-- ASOF JOIN: match each rate to the latest Treasury yield on or before its
-- date. Rates and yields are not always published on the same days (bond
-- market holidays), so an exact-date join would leave gaps.
asof left join treasury as t
    on r.rate_date >= t.treasury_date
inner join series as s
    on s.series_id = r.series_id
