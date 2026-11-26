{{ config(materialized='table') }}

-- Phase 2 weekly labels.
-- Features use past prices; labels use future prices.
-- Never use label values as model input features.

with features as (
    select as_of, ticker, role, adj_close
    from {{ ref('weekly_features') }}
),

calendar as (
    select trade_date, day_idx
    from {{ ref('int_phase2_calendar') }}
),

priced as (
    select ticker, trade_date, day_idx, adj_close
    from {{ ref('int_phase2_daily_prices') }}
),

week_indices as (
    select
        f.*,
        c.day_idx as as_of_idx
    from features f
    join calendar c
      on f.as_of = c.trade_date
),

forward_prices as (
    select
        w.as_of,
        w.ticker,
        min(p.adj_close) as fwd_min_adj_close,
        count(distinct p.day_idx) as observed_forward_days,
        max(p.day_idx) as last_observed_idx
    from week_indices w
    left join priced p
      on p.ticker = w.ticker
     and p.day_idx > w.as_of_idx
     and p.day_idx <= w.as_of_idx + 60
    group by w.as_of, w.ticker
),

calendar_end as (
    select max(day_idx) as max_day_idx
    from calendar
),

base as (
    select
        w.as_of,
        w.ticker,
        w.role,
        least(
            60,
            greatest(0, c.max_day_idx - w.as_of_idx)
        ) as fwd_days_available,
        p.fwd_min_adj_close,
        safe_divide(p.fwd_min_adj_close, w.adj_close) - 1
            as fwd_min_return,
        p.observed_forward_days,
        p.last_observed_idx,
        w.as_of_idx,
        c.max_day_idx
    from week_indices w
    left join forward_prices p
      on w.as_of = p.as_of
     and w.ticker = p.ticker
    cross join calendar_end c
),

statuses as (
    select
        *,
        case
            -- A complete calendar alone does not guarantee complete
            -- ticker prices. Missing observations remain pending.
            when fwd_days_available < 60 then 'pending'
            when observed_forward_days < 60 then 'pending'
            else 'final'
        end as label_status
    from base
),

labeled as (
    select
        *,
        case
            when label_status = 'pending' then cast(null as int64)
            when fwd_min_return <= -0.20 then 1
            else 0
        end as label_drop_20pct_60d
    from statuses
)

select
    as_of,
    ticker,
    role,
    fwd_days_available,
    fwd_min_adj_close,
    fwd_min_return,
    label_drop_20pct_60d,
    label_status,

    case
        when label_status = 'pending' then 'unlabeled'
        when as_of between '2021-01-08' and '2024-06-28'
            then 'train'
        when as_of between '2024-10-04' and '2025-06-27'
            then 'validation'
        when as_of >= '2025-10-03'
            then 'test'
        else 'gap'
    end as split,

    current_timestamp() as computed_at

from labeled
