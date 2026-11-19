-- Latest value of each national market indicator and its change from the
-- same month or quarter a year earlier: the national panel for report
-- sections 5, 6, and 11. Year-over-year comparison is used because several
-- series (the Realtor.com counts) are not seasonally adjusted.

with indicators as (

    select * from {{ ref('fct_national_market_indicators') }}

),

latest as (

    select *
    from indicators
    qualify row_number() over (partition by series_id order by observation_date desc) = 1

)

select
    l.series_id,
    l.report_section,
    l.section_name,
    l.metric_name,
    l.units,
    l.seasonal_adjustment,
    l.publisher,
    l.is_derived,
    l.display_order,
    l.observation_date as as_of,
    l.value,
    y.value as value_1y_ago,
    l.change_type,
    -- Counts and levels change in percent; rates and shares in percentage points
    case
        when l.change_type = 'pct' then round(100 * (l.value / y.value - 1), 2)
        when l.change_type = 'pts' then round(l.value - y.value, 2)
    end as change_1y
from latest as l
-- Exact date a year earlier (FRED dates months and quarters by their first day)
left join indicators as y
    on y.series_id = l.series_id
    and y.observation_date = cast(l.observation_date - interval 1 year as date)
