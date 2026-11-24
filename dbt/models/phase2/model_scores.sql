{{ config(
    materialized='table',
    enabled=(target.name == 'dev')
) }}

-- Development-only scores.
-- Rank each stock relative to the universe, excluding our basket
-- from the ranking population.

with predictions as (

    select *
    from {{ ref('model_predictions') }}
    where model_name = 'logistic'

),

ranked as (

    select
        p.*,

        (
            select count(*)
            from predictions u
            where u.as_of = p.as_of
              and u.role = 'universe'
        ) as universe_size,

        1 + (
            select count(*)
            from predictions u
            where u.as_of = p.as_of
              and u.role = 'universe'
              and u.prob_drop_20pct_60d > p.prob_drop_20pct_60d
        ) as rank_in_universe

    from predictions p

),

scored as (

    select
        *,
        lag(prob_drop_20pct_60d) over (
            partition by ticker
            order by as_of
        ) as previous_probability
    from ranked

)

select
    ticker,
    as_of,
    prob_drop_20pct_60d,
    rank_in_universe,
    model_version,
    trained_at,
    model_name,
    role,
    universe_size,

    least(
        1.0,
        safe_divide(rank_in_universe, universe_size)
    ) as pct_rank_in_universe,

    prob_drop_20pct_60d - previous_probability
        as prob_change_1w,

    scored_at

from scored
