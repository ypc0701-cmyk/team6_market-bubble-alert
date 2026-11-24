{{ config(
    materialized='table',
    enabled=(target.name == 'dev')
) }}

-- Development-only predictions from the logistic regression model.
-- This is NOT the final four-model production implementation.

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

),

predictions as (

    select *
    from ML.PREDICT(
        MODEL `market-bubble-alert.marts_dev.phase2_logistic_dev`,
        (select * from scoring_input)
    )

)

select
    as_of,
    ticker,
    role,
    'logistic' as model_name,
    'logistic-dev-1795492321503' as model_version,
    timestamp_millis(1795492321503) as trained_at,

    (
        select p.prob
        from unnest(predicted_label_drop_20pct_60d_probs) p
        where cast(p.label as string) = '1'
    ) as prob_drop_20pct_60d,

    split,
    current_timestamp() as scored_at

from predictions
