-- credit_daily: the credit gauge of Methodology section 2 [M §2, M §6]. HYG / IEF, its distance from
-- the trailing 126-trading-day high, and the normal / watch / stress status. One row per trading
-- day on which both ETFs have a price.
{{ config(
    materialized='table',
    partition_by=({'field': 'trade_date', 'data_type': 'date'} if target.type == 'bigquery' else none)
) }}

with cal as (
    select * from {{ ref('int_trading_calendar') }}
),

prices as (
    select trade_date, ticker, adj_close
    from {{ ref('stg_prices') }}
    where ticker in ('HYG', 'IEF')
),

ratio as (
    select
        c.trade_date,
        c.day_idx,
        hyg.adj_close as hyg_adj_close,
        ief.adj_close as ief_adj_close,
        hyg.adj_close / ief.adj_close as credit_ratio
    from cal as c
    join prices as hyg on hyg.trade_date = c.trade_date and hyg.ticker = 'HYG'
    join prices as ief on ief.trade_date = c.trade_date and ief.ticker = 'IEF'
),

windowed as (
    select
        *,
        max(credit_ratio) over (order by day_idx range between 125 preceding and current row) as ratio_high_126,
        count(credit_ratio) over (order by day_idx range between 125 preceding and current row) as ratio_window_days
    from ratio
)

select
    trade_date,
    hyg_adj_close,
    ief_adj_close,
    credit_ratio,
    ratio_window_days,
    ratio_high_126,
    credit_ratio / ratio_high_126 - 1 as credit_distance,
    case
        when credit_ratio / ratio_high_126 - 1 <= -0.06 then 'stress'
        when credit_ratio / ratio_high_126 - 1 <= -0.03 then 'watch'
        else 'normal'
    end as credit_status,
    -- FRED BAMLH0A0HYM2 is the named cross-check and never an input [M §2]. No FRED series has
    -- landed in raw yet (Lane 1 open item); the column is reserved and NULL until it does.
    cast(null as {{ dbt.type_float() }}) as fred_hy_oas,
    {{ dbt.current_timestamp() }} as computed_at
from windowed
