{{ config(materialized='table') }}

-- Phase 2 weekly features
-- All calculations use prices available on or before as_of.
-- The original speculative basket is scored but never used
-- when calculating universe breadth.

with calendar as (
    select *
    from {{ ref('int_phase2_calendar') }}
),

prices as (
    select *
    from {{ ref('int_phase2_daily_prices') }}
),

members as (
    select *
    from {{ ref('int_phase2_members') }}
),

weeks as (
    select trade_date as as_of, day_idx
    from calendar
    where is_week_end
),

weekly_stocks as (
    select
        w.as_of,
        w.day_idx,
        p.ticker,
        m.role,
        m.listing_date,
        p.adj_close,
        p.close
    from weeks w
    join prices p
      on p.trade_date = w.as_of
    join members m
      on p.ticker = m.ticker
     and m.added_date <= w.as_of
     and (m.removed_date is null
          or w.as_of < m.removed_date)
     and m.listing_date <= w.as_of
),

reference_returns as (
    select
        day_idx,
        max(if(ticker = '^GSPC', daily_return, null))
            as spx_return,
        max(if(ticker = 'ARKK', daily_return, null))
            as arkk_return
    from prices
    where ticker in ('^GSPC', 'ARKK')
    group by day_idx
),

credit_prices as (
    select
        day_idx,
        safe_divide(
            max(if(ticker = 'HYG', adj_close, null)),
            max(if(ticker = 'IEF', adj_close, null))
        ) as credit_ratio
    from prices
    where ticker in ('HYG', 'IEF')
    group by day_idx
),

stock_history as (
    select
        w.as_of,
        w.day_idx as as_of_idx,
        w.ticker,
        w.role,
        w.listing_date,
        w.adj_close,
        w.close,
        h.day_idx,
        h.adj_close as historical_close,
        h.close as historical_unadjusted_close,
        h.volume,
        h.daily_return,
        h.daily_log_return,
        r.spx_return,
        r.arkk_return
    from weekly_stocks w
    join prices h
      on h.ticker = w.ticker
     and h.day_idx between w.day_idx - 251
                         and w.day_idx
    left join reference_returns r
      on h.day_idx = r.day_idx
),

stock_aggregates as (
    select
        as_of,
        as_of_idx,
        ticker,
        role,
        listing_date,
        any_value(adj_close) as adj_close,
        any_value(close) as close,

        avg(if(
            day_idx >= as_of_idx - 19,
            historical_unadjusted_close * volume,
            null
        )) as adv_20d_usd,

        safe_divide(
            any_value(adj_close),
            max(historical_close)
        ) - 1 as drawdown_252,

        safe_divide(
            any_value(adj_close),
            max(if(day_idx = as_of_idx - 20,
                   historical_close, null))
        ) - 1 as ret_20d,

        safe_divide(
            any_value(adj_close),
            max(if(day_idx = as_of_idx - 60,
                   historical_close, null))
        ) - 1 as ret_60d,

        safe_divide(
            any_value(adj_close),
            max(if(day_idx = as_of_idx - 120,
                   historical_close, null))
        ) - 1 as ret_120d,

        stddev_samp(if(
            day_idx >= as_of_idx - 59,
            daily_log_return,
            null
        )) * sqrt(252) as vol_60d,

        safe_divide(
            avg(if(day_idx >= as_of_idx - 4,
                   cast(volume as float64), null)),
            avg(if(day_idx >= as_of_idx - 59,
                   cast(volume as float64), null))
        ) as volume_ratio_60d,

        safe_divide(
            covar_samp(
                if(day_idx >= as_of_idx - 119,
                   daily_return, null),
                if(day_idx >= as_of_idx - 119,
                   spx_return, null)
            ),
            var_samp(if(day_idx >= as_of_idx - 119,
                        spx_return, null))
        ) as beta_spx_120d,

        safe_divide(
            covar_samp(
                if(day_idx >= as_of_idx - 119,
                   daily_return, null),
                if(day_idx >= as_of_idx - 119,
                   arkk_return, null)
            ),
            var_samp(if(day_idx >= as_of_idx - 119,
                        arkk_return, null))
        ) as beta_arkk_120d

    from stock_history
    group by as_of, as_of_idx, ticker, role, listing_date
),

market_history as (
    select
        w.as_of,
        w.day_idx as as_of_idx,
        p.day_idx,
        p.ticker,
        p.adj_close
    from weeks w
    join prices p
      on p.day_idx between w.day_idx - 251
                           and w.day_idx
     and p.ticker = '^GSPC'
),

market_features as (
    select
        as_of,
        safe_divide(
            max(if(day_idx = as_of_idx,
                   adj_close, null)),
            max(adj_close)
        ) - 1 as spx_distance
    from market_history
    group by as_of
),

credit_history as (
    select
        w.as_of,
        w.day_idx as as_of_idx,
        c.day_idx,
        c.credit_ratio
    from weeks w
    join credit_prices c
      on c.day_idx between w.day_idx - 125
                            and w.day_idx
),

credit_features as (
    select
        as_of,
        safe_divide(
            max(if(day_idx = as_of_idx,
                   credit_ratio, null)),
            max(credit_ratio)
        ) - 1 as credit_distance
    from credit_history
    group by as_of
),

base_features as (
    select
        s.as_of,
        s.ticker,
        s.role,
        s.adj_close,

        -- Actual benchmark trading-day count since listing.
        (
            select count(*)
            from calendar c
            where c.trade_date between s.listing_date
                                   and s.as_of
        ) as observed_days_listed,

        s.listing_date,
        s.close,
        s.adv_20d_usd,
        s.drawdown_252,
        s.ret_20d,
        s.ret_60d,
        s.ret_120d,
        s.vol_60d,
        s.volume_ratio_60d,
        s.beta_spx_120d,
        s.beta_arkk_120d,
        m.spx_distance,
        c.credit_distance
    from stock_aggregates s
    left join market_features m
      on s.as_of = m.as_of
    left join credit_features c
      on s.as_of = c.as_of
),

screened as (
    select
        *,
        observed_days_listed as days_listed,
        least(observed_days_listed, 1260)
            as days_listed_capped,

        (
            observed_days_listed >= 126
            and close > 2
            and adv_20d_usd >= 5000000
            and drawdown_252 is not null
        ) as is_screen_eligible
    from base_features
    where observed_days_listed >= 60
),

breadth as (
    select
        as_of,
        safe_divide(
            countif(drawdown_252 <= -0.25),
            count(*)
        ) as universe_breadth
    from screened
    where role = 'universe'
      and is_screen_eligible
    group by as_of
),

final_features as (
    select
        s.*,
        b.universe_breadth,

        (
            s.is_screen_eligible
            and s.ret_20d is not null
            and s.ret_60d is not null
            and s.ret_120d is not null
            and s.vol_60d is not null
            and s.volume_ratio_60d is not null
            and s.beta_spx_120d is not null
            and s.beta_arkk_120d is not null
            and s.spx_distance is not null
            and s.credit_distance is not null
            and b.universe_breadth is not null
        ) as is_model_eligible
    from screened s
    left join breadth b
      on s.as_of = b.as_of
)

select
    as_of,
    ticker,
    role,
    adj_close,
    days_listed,
    adv_20d_usd,
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
    is_screen_eligible,
    universe_breadth,
    is_model_eligible,
    current_timestamp() as computed_at
from final_features
