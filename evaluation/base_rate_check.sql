-- R3 pre-registered base-rate check (Lane 3, #81).
-- Run ONCE on training rows, BEFORE any model is trained or any validation/test number is looked at.
-- Training row (contract v0.3, weekly_labels): role = 'universe' AND is_model_eligible
--   AND split = 'train' AND label_drop_20pct_60d IS NOT NULL.
-- Rule: share of 1s in [10%, 40%] -> the 20% / 60-day label stands.
--       above 40% -> threshold moves to 25%; below 10% -> to 15%; rerun once on the new
--       threshold and log the result in docs/decision_log.md either way. No other label change.
--
-- Dataset: `marts` in prod. For a dev build replace `marts.` with your dev dataset (e.g. `marts_dev.`).

with train_rows as (
    select
        l.as_of,
        l.ticker,
        l.label_drop_20pct_60d as label,
        l.fwd_min_return
    from `market-bubble-alert.marts.weekly_labels` as l
    join `market-bubble-alert.marts.weekly_features` as f
        on f.as_of = l.as_of and f.ticker = l.ticker
    where l.role = 'universe'
        and f.is_model_eligible
        and l.split = 'train'
        and l.label_drop_20pct_60d is not null
),

by_group as (
    select
        cast(extract(year from as_of) as string) as grp,
        count(*) as n_rows,
        count(distinct ticker) as n_tickers,
        count(distinct as_of) as n_weeks,
        avg(label) as base_rate_20pct,
        -- The two fallback thresholds, shown for information only; R3 picks by the 20% result alone.
        avg(case when fwd_min_return <= -0.25 then 1 else 0 end) as share_at_25pct,
        avg(case when fwd_min_return <= -0.15 then 1 else 0 end) as share_at_15pct
    from train_rows
    group by 1
    union all
    select
        'ALL TRAIN' as grp,
        count(*),
        count(distinct ticker),
        count(distinct as_of),
        avg(label),
        avg(case when fwd_min_return <= -0.25 then 1 else 0 end),
        avg(case when fwd_min_return <= -0.15 then 1 else 0 end)
    from train_rows
)

select
    grp,
    n_rows,
    n_tickers,
    n_weeks,
    round(base_rate_20pct, 4) as base_rate_20pct,
    round(share_at_25pct, 4) as share_at_25pct,
    round(share_at_15pct, 4) as share_at_15pct,
    case
        when grp != 'ALL TRAIN' then null
        when base_rate_20pct > 0.40 then 'MOVE THRESHOLD TO 25% (R3), rerun once and log'
        when base_rate_20pct < 0.10 then 'MOVE THRESHOLD TO 15% (R3), rerun once and log'
        else 'LABEL STANDS: 20% / 60 trading days (R3)'
    end as r3_verdict
from by_group
order by grp = 'ALL TRAIN' desc, grp
