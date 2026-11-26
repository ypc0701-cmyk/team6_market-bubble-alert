{{ config(materialized='ephemeral') }}

-- Phase 2 uses the full historical S&P 500 calendar.
-- Unlike Phase 1, there is no October 2023 calendar floor.

with benchmark_days as (

    select distinct trade_date
    from {{ ref('stg_prices') }}
    where ticker = '^GSPC'
      and adj_close > 0

),

numbered_days as (

    select
        trade_date,
        row_number() over (
            order by trade_date
        ) as day_idx,
        date_trunc(trade_date, week(monday)) as week_start
    from benchmark_days

)

select
    trade_date,
    day_idx,
    week_start,
    row_number() over (
        partition by week_start
        order by trade_date desc
    ) = 1 as is_week_end

from numbered_days
