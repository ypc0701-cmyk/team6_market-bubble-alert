-- daily_drawdowns: the per-ticker math of Methodology section 2 [M §2, M §6].
-- One row per (trade_date, ticker) for every tracked symbol whose membership span covers the day,
-- is already listed, and has a price that day. Nothing is forward-filled [C 6, C 7].
{{ config(
    materialized='table',
    partition_by=({'field': 'trade_date', 'data_type': 'date'} if target.type == 'bigquery' else none),
    cluster_by=(['ticker'] if target.type == 'bigquery' else none)
) }}

with cal as (
    select * from {{ ref('int_trading_calendar') }}
),

members as (
    select
        ticker,
        basket,
        listing_date,
        added_date,
        coalesce(removed_date, date '9999-12-31') as removed_before
    from {{ ref('basket_members') }}
),

-- days_listed is counted on the benchmark calendar from listing_date, not from the first
-- backfilled row [M §2, contract §3 "Young listings"]. For a listing older than the warehouse the
-- pre-backfill trading days are estimated at 252 per 365 calendar days; both young-listing rules
-- are thresholds (20 and 60 days) that such a name cleared years ago, so the estimate only has to
-- be large, not exact. A listing inside the warehouse is counted exactly.
listing_idx as (
    select
        m.ticker,
        m.listing_date,
        min(c.day_idx) as first_idx,
        case
            when m.listing_date < min(c.cal_start)
                then cast(floor({{ dbt.datediff('m.listing_date', 'min(c.cal_start)', 'day') }} * 252.0 / 365.0) as {{ dbt.type_int() }})
            else 0
        end as pre_warehouse_days
    from (select distinct ticker, listing_date from members) as m
    join cal as c on c.trade_date >= m.listing_date
    group by m.ticker, m.listing_date
),

priced as (
    select
        c.trade_date,
        c.day_idx,
        m.ticker,
        m.basket,
        p.adj_close,
        c.day_idx - li.first_idx + 1 + li.pre_warehouse_days as days_listed
    from cal as c
    join members as m
        on m.added_date <= c.trade_date
        and c.trade_date < m.removed_before
        and m.listing_date <= c.trade_date
    join listing_idx as li
        on li.ticker = m.ticker and li.listing_date = m.listing_date
    join {{ ref('stg_prices') }} as p
        on p.ticker = m.ticker and p.trade_date = c.trade_date
),

-- Reference high: the highest adj_close over the trailing 252 trading days including today, with
-- the listing's first 20 trading days excluded so an IPO pop never becomes the yardstick [M §2].
-- RANGE over day_idx counts trading days even when the ticker is missing a day.
windowed as (
    select
        *,
        max(case when days_listed > 20 then adj_close end) over (
            partition by ticker order by day_idx
            range between 251 preceding and current row
        ) as reference_high,
        count(case when days_listed > 20 then adj_close end) over (
            partition by ticker order by day_idx
            range between 251 preceding and current row
        ) as reference_window_days
    from priced
)

select
    w.trade_date,
    w.ticker,
    w.basket,
    w.adj_close,
    w.days_listed,
    w.reference_window_days,
    w.reference_high,
    case when w.reference_high is not null then w.adj_close / w.reference_high - 1 end as drawdown,
    w.days_listed >= 60 as is_mature,
    (w.days_listed >= 60 and w.reference_high is not null and w.basket in ('speculative', 'megacap')) as is_signal_eligible,
    case when w.reference_high is not null then w.adj_close / w.reference_high - 1 <= -0.25 end as is_broken,
    case when p6.adj_close is not null then w.adj_close / p6.adj_close - 1 end as return_6m,
    {{ dbt.current_timestamp() }} as computed_at
from windowed as w
left join priced as p6
    on p6.ticker = w.ticker and p6.day_idx = w.day_idx - 126
