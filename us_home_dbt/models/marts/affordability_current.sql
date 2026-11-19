-- Affordability headline numbers per region (report section 4, v1): the
-- monthly principal-and-interest payment on the typical home at the current
-- 30-year rate, the same payment a year earlier, the price-to-rent ratio, and
-- (US only) the payment as a share of median household income.

{% set down_pct = var('affordability_down_payment_pct') %}
{% set term_years = var('affordability_loan_term_years') %}

with current_values as (

    select * from {{ ref('home_values_rents_current') }}
    where typical_home_value is not null

),

monthly_values as (

    select region_id, month_start_date, typical_home_value
    from {{ ref('fct_home_values_rents_monthly') }}
    where typical_home_value is not null

),

-- Freddie Mac 30-year fixed: the benchmark for "today's rate"
rate_history as (

    select rate_date, rate_pct
    from {{ ref('fct_mortgage_rates') }}
    where series_id = 'MORTGAGE30US'

),

rate_now as (

    select rate_date, rate_pct
    from rate_history
    qualify row_number() over (order by rate_date desc) = 1

),

-- Latest weekly rate on or before the same date a year earlier
rate_year_ago as (

    select
        p.rate_date,
        p.rate_pct
    from rate_now as n
    asof inner join rate_history as p
        on cast(n.rate_date - interval 1 year as date) >= p.rate_date

),

-- Median household income in current dollars (annual, about a year behind)
income as (

    select
        year(observation_date) as income_year,
        value as median_household_income
    from {{ ref('stg_fred__observations') }}
    where series_id = 'MEHOINUSA646N'
    qualify row_number() over (order by observation_date desc) = 1

),

payments as (

    select
        c.*,
        n.rate_date as rate_as_of,
        n.rate_pct as mortgage_rate_30y_pct,
        c.typical_home_value * (1 - {{ down_pct }} / 100.0) as loan_amount,
        {{ monthly_payment(
            'c.typical_home_value * (1 - ' ~ down_pct ~ ' / 100.0)',
            'n.rate_pct', term_years) }} as monthly_payment,
        m.typical_home_value as home_value_1y_ago,
        y.rate_date as rate_1y_ago_as_of,
        y.rate_pct as mortgage_rate_30y_1y_ago_pct,
        {{ monthly_payment(
            'm.typical_home_value * (1 - ' ~ down_pct ~ ' / 100.0)',
            'y.rate_pct', term_years) }} as monthly_payment_1y_ago
    from current_values as c
    cross join rate_now as n
    cross join rate_year_ago as y
    -- Home value in the same month a year before the latest home value
    left join monthly_values as m
        on m.region_id = c.region_id
        and m.month_start_date = cast(date_trunc('month', c.home_value_as_of) - interval 12 month as date)

)

select
    p.region_id,
    p.geography_level,
    p.region_name,
    p.zip_code,
    p.state_code,
    p.state_name,
    p.city,
    p.metro_name,
    p.county_name,
    p.home_value_as_of,
    p.typical_home_value,
    p.rate_as_of,
    p.mortgage_rate_30y_pct,
    {{ down_pct }} as down_payment_pct,
    {{ term_years }} as loan_term_years,
    round(p.loan_amount, 0) as loan_amount,
    round(p.monthly_payment, 0) as monthly_payment,
    p.home_value_1y_ago,
    p.rate_1y_ago_as_of,
    p.mortgage_rate_30y_1y_ago_pct,
    round(p.monthly_payment_1y_ago, 0) as monthly_payment_1y_ago,
    round(100 * (p.monthly_payment / p.monthly_payment_1y_ago - 1), 2) as monthly_payment_change_1y_pct,
    p.rent_as_of,
    p.typical_rent,
    -- Only when value and rent describe the same month
    case
        when p.rent_as_of = p.home_value_as_of
            then round(p.typical_home_value / (12 * p.typical_rent), 1)
    end as price_to_rent_ratio,
    -- National only: this income series covers the US as a whole
    case when p.geography_level = 'national' then i.income_year end as income_year,
    case when p.geography_level = 'national' then i.median_household_income end as median_household_income,
    case
        when p.geography_level = 'national'
            then round(100 * 12 * p.monthly_payment / i.median_household_income, 1)
    end as payment_to_income_pct
from payments as p
cross join income as i
