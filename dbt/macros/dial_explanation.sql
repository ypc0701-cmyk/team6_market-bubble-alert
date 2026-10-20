{% macro dial_explanation() %}
{#- One templated sentence for the verdict card [L4]. Lane 3 owns the template; the dashboard
    renders it verbatim. Expects the daily_signals columns to be in scope.
    e.g. "DIVERGENCE: armed since 2026-02-11; 7 of 11 speculative names broken; S&P 1.8% off its high." -#}
concat(
    dial_label, ': ',
    case when is_armed then concat('armed since ', cast(armed_since as {{ dbt.type_string() }})) else 'not armed' end,
    '; ',
    case when spec_members_valid > 0
         then concat(cast(spec_members_broken as {{ dbt.type_string() }}), ' of ', cast(spec_members_valid as {{ dbt.type_string() }}), ' speculative names broken')
         else 'no speculative member with valid data' end,
    '; S&P ', {% if target.type == 'bigquery' %}format('%.1f', abs(spx_distance) * 100){% else %}printf('%.1f', abs(spx_distance) * 100){% endif %}, '% off its high',
    case
        when badge = 'off_pattern' then ' (off-pattern: decline without the junk-first precedent)'
        when badge = 'credit_only' then ' (credit-only: funding stress with no equity pattern)'
        else ''
    end,
    '.'
)
{% endmacro %}
