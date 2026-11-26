-- R3 pre-registered training-only base-rate check.
-- Training must not proceed if the rate falls outside [0.10, 0.40].

with train_rows as (
    select l.label_drop_20pct_60d as label
    from {{ ref('weekly_labels') }} l
    join {{ ref('weekly_features') }} f
        on f.as_of = l.as_of
        and f.ticker = l.ticker
    where l.role = 'universe'
      and f.is_model_eligible
      and l.split = 'train'
      and l.label_drop_20pct_60d is not null
),

summary as (
    select
        count(*) as n_train_rows,
        avg(label) as base_rate
    from train_rows
)

select *
from summary
where n_train_rows = 0
   or base_rate < 0.10
   or base_rate > 0.40
