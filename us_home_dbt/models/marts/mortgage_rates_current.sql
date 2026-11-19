-- Latest value of each mortgage rate, with its recent movement: the headline
-- numbers for report section 3.

with rates as (

    select * from {{ ref('fct_mortgage_rates') }}

),

latest as (

    select *
    from rates
    qualify row_number() over (partition by series_id order by rate_date desc) = 1

),

-- Rate a week and a year before the latest date. ASOF picks the latest
-- observation on or before the target date, so it works for weekly and daily
-- series alike (and skips holidays).
week_ago as (

    select
        l.series_id,
        p.rate_pct as rate_1w_ago_pct
    from latest as l
    asof left join rates as p
        on p.series_id = l.series_id
        and l.rate_date - 7 >= p.rate_date

),

year_ago as (

    select
        l.series_id,
        p.rate_pct as rate_1y_ago_pct
    from latest as l
    asof left join rates as p
        on p.series_id = l.series_id
        and cast(l.rate_date - interval 1 year as date) >= p.rate_date

),

range_52w as (

    select
        l.series_id,
        min(p.rate_pct) as low_52w_pct,
        max(p.rate_pct) as high_52w_pct
    from latest as l
    inner join rates as p
        on p.series_id = l.series_id
        and p.rate_date > cast(l.rate_date - interval 1 year as date)
    group by l.series_id

)

select
    l.series_id,
    l.rate_name,
    l.rate_source,
    l.loan_type,
    l.term_years,
    l.frequency,
    l.display_order,
    l.rate_date as rate_as_of,
    l.rate_pct,
    round(l.rate_pct - w.rate_1w_ago_pct, 3) as change_1w_pct_pts,
    round(l.rate_pct - y.rate_1y_ago_pct, 3) as change_1y_pct_pts,
    r.low_52w_pct,
    r.high_52w_pct,
    l.treasury_10y_pct,
    l.spread_to_treasury_pct_pts
from latest as l
left join week_ago as w on w.series_id = l.series_id
left join year_ago as y on y.series_id = l.series_id
left join range_52w as r on r.series_id = l.series_id
