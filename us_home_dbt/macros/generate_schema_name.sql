{#
    By default dbt prefixes custom schemas with the target schema, so
    +schema: staging would create "main_staging". This override uses the
    custom schema name as is ("staging", "marts"), and falls back to the
    target schema (main) for models without one.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
