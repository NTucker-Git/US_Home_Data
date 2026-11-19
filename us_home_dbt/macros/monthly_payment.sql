{#
    Monthly principal-and-interest payment on a fixed-rate loan, using the
    standard amortization formula:  P * r / (1 - (1 + r)^-n)
    where P is the loan amount, r the monthly interest rate, and n the number
    of monthly payments. annual_rate_pct is a percent (7.11 means 7.11%).
#}
{% macro monthly_payment(principal, annual_rate_pct, term_years) %}
    (
        ({{ principal }}) * (({{ annual_rate_pct }}) / 1200.0)
        / (1 - pow(1 + ({{ annual_rate_pct }}) / 1200.0, -12 * ({{ term_years }})))
    )
{% endmacro %}
