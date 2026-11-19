-- National market indicators for report sections 5 (market activity),
-- 6 (new supply and construction), and 11 (market risk): one row per series
-- per observation date, labeled from the market_panel_series seed. Includes
-- one derived series, the share of active listings with a price cut.

with observations as (

    select * from {{ ref('stg_fred__observations') }}

),

series as (

    select * from {{ ref('market_panel_series') }}

),

fred_values as (

    select
        o.series_id,
        o.observation_date,
        o.value
    from observations as o
    inner join series as s
        on s.series_id = o.series_id
        and not s.is_derived

),

-- Share of active listings with a price cut, from two Realtor.com counts
price_reduced_share as (

    select
        'PRICE_REDUCED_SHARE' as series_id,
        reduced.observation_date,
        round(100 * reduced.value / active.value, 2) as value
    from observations as reduced
    inner join observations as active
        on active.observation_date = reduced.observation_date
        and active.series_id = 'ACTLISCOUUS'
    where reduced.series_id = 'PRIREDCOUUS'

),

all_values as (

    select * from fred_values
    union all
    select * from price_reduced_share

)

select
    s.series_id,
    s.report_section,
    s.section_name,
    s.metric_name,
    s.units,
    s.seasonal_adjustment,
    s.publisher,
    s.change_type,
    s.is_derived,
    s.display_order,
    v.observation_date,
    v.value
from all_values as v
inner join series as s
    on s.series_id = v.series_id
