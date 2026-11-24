{{ config(materialized='view') }}

-- Phase 2 training input.
-- Only eligible universe stocks with known outcomes.
-- Our original 11 speculative stocks are never training rows.

select
    f.as_of,
    f.ticker,
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
    f.universe_breadth,
    l.split,
    l.label_drop_20pct_60d
from {{ ref('weekly_features') }} f
join {{ ref('weekly_labels') }} l
  on f.as_of = l.as_of
 and f.ticker = l.ticker
where f.role = 'universe'
  and f.is_model_eligible
  and l.label_drop_20pct_60d is not null
  and l.label_status = 'final'
  and l.split in ('train', 'validation', 'test')
