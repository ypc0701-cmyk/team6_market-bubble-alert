-- Verify labels use the next 60 benchmark trading days.
-- The current as_of date must not be included.

with calendar as (
    select trade_date, day_idx
    from {{ ref('int_phase2_calendar') }}
),

expected as (
    select
        l.as_of,
        l.ticker,
        min(p.adj_close) as expected_min
    from {{ ref('weekly_labels') }} l
    join calendar c
      on c.trade_date = l.as_of
    left join {{ ref('stg_prices') }} p
      on p.ticker = l.ticker
    left join calendar future
      on future.trade_date = p.trade_date
     and future.day_idx > c.day_idx
     and future.day_idx <= c.day_idx + 60
    where future.trade_date is not null
    group by l.as_of, l.ticker
)

select
    l.as_of,
    l.ticker,
    l.fwd_min_adj_close,
    e.expected_min
from {{ ref('weekly_labels') }} l
left join expected e
  on l.as_of = e.as_of
 and l.ticker = e.ticker
where
    l.fwd_min_adj_close is distinct from e.expected_min
