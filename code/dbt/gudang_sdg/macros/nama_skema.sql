{# Skema sesuai nama yang dinyatakan (gold, dp, rujukan), tanpa awalan skema target. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}
