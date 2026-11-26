{{ config(
    materialized='table',
    enabled=(target.name == 'dev')
) }}

{% set models = [
    {
        'name': 'baseline_drawdown',
        'feature': 'drawdown_252',
        'created_ms': var('phase2_model_timestamps')['baseline_drawdown']
    },
    {
        'name': 'baseline_vol',
        'feature': 'vol_60d',
        'created_ms': var('phase2_model_timestamps')['baseline_vol']
    },
    {
        'name': 'logistic',
        'feature': none,
        'created_ms': var('phase2_model_timestamps')['logistic']
    },
    {
        'name': 'boosted_trees',
        'feature': none,
        'created_ms': var('phase2_model_timestamps')['boosted_trees']
    }
] %}

with scoring_input as (

    select
        f.as_of,
        f.ticker,
        f.role,
        l.split,
        f.drawdown_252,
        f.ret_20d,
        f.ret_60d,
        f.ret_120d,
        f.vol_60d,
        f.volume_ratio_60d,
        f.beta_spx_120d,
        f.beta_arkk_120d,
        f.days_listed_capped,
        f.spx_distance,
        f.credit_distance,
        f.universe_breadth

    from {{ ref('weekly_features') }} f

    join {{ ref('weekly_labels') }} l
        on f.as_of = l.as_of
        and f.ticker = l.ticker

    where f.is_model_eligible

)

{% for model in models %}

, predictions_{{ loop.index }} as (

    select *
    from ML.PREDICT(
        MODEL `{{ target.database }}.marts_dev.phase2_{{ model.name }}_dev`,
        (
            select
                as_of,
                ticker,
                role,
                split,
                {% if model.feature %}
                    {{ model.feature }}
                {% else %}
                    drawdown_252,
                    ret_20d,
                    ret_60d,
                    ret_120d,
                    vol_60d,
                    volume_ratio_60d,
                    beta_spx_120d,
                    beta_arkk_120d,
                    days_listed_capped,
                    spx_distance,
                    credit_distance,
                    universe_breadth
                {% endif %}
            from scoring_input
        )
    )

)

{% endfor %}

{% for model in models %}

select
    as_of,
    ticker,
    role,
    '{{ model.name }}' as model_name,

    '{{ model.name }}-dev-{{ model.created_ms }}' as model_version,

    timestamp_millis({{ model.created_ms }}) as trained_at,

    (
        select p.prob
        from unnest(predicted_label_drop_20pct_60d_probs) p
        where cast(p.label as string) = '1'
    ) as prob_drop_20pct_60d,

    split,
    current_timestamp() as scored_at

from predictions_{{ loop.index }}

{% if not loop.last %}
union all
{% endif %}

{% endfor %}
