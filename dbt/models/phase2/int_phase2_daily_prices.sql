{{ config(materialized='ephemeral') }}

-- Phase 2 daily price foundation.
-- Uses the full S&P 500 trading calendar, including 2020 onward.
-- Does not modify Phase 1 models.

with daily_prices as (

    select
        c.trade_date,
        c.day_idx,
        c.week_start,
        c.is_week_end,
        p.ticker,
        p.adj_close,
        p.close,
        p.volume

    from {{ ref('stg_prices') }} as p

    inner join {{ ref('int_phase2_calendar') }} as c
        on p.trade_date = c.trade_date

    where p.adj_close > 0

),

previous_prices as (

    select
        *,
        lag(adj_close) over (
            partition by ticker
            order by day_idx
        ) as previous_adj_close,

        lag(day_idx) over (
            partition by ticker
            order by day_idx
        ) as previous_day_idx

    from daily_prices

)

select
    trade_date,
    day_idx,
    week_start,
    is_week_end,
    ticker,
    adj_close,
    close,
    volume,

    case
        when previous_day_idx = day_idx - 1
        then safe_divide(adj_close, previous_adj_close) - 1
    end as daily_return,

    case
        when previous_day_idx = day_idx - 1
        then ln(safe_divide(adj_close, previous_adj_close))
    end as daily_log_return

from previous_prices
