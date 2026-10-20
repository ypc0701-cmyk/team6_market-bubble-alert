-- The trading calendar [C 6]: a trading day is any trade_date on which the benchmark (^GSPC) has a
-- row in staging. day_idx is the 1-based position on that calendar; every window in the marts is
-- expressed in day_idx so "252 trading days" never silently becomes 252 ticker rows or 252
-- calendar days. cal_start is the first day in the warehouse (the backfill start).
--
-- Partial loads (decided Oct 18): the daily run can fire before the provider has served every
-- ticker for the newest day, and the missing rows arrive on the next run. So the newest trade_date
-- in staging is held back while any in-force, already-listed ticker has no row on it. Only the
-- newest day is held back: a gap on an older day is a real event (a halt, a provider miss) and
-- stays visible rather than erasing a day of history from every mart.
{{ config(materialized='ephemeral') }}

with members as (
    select
        ticker,
        basket,
        listing_date,
        added_date,
        coalesce(removed_date, date '9999-12-31') as removed_before
    from {{ ref('basket_members') }}
),

benchmark_days as (
    select distinct p.trade_date
    from {{ ref('stg_prices') }} as p
    join members as m on m.ticker = p.ticker and m.basket = 'benchmark'
),

-- expected: tickers whose span covers the day and that are already listed; present: of those, with a row
coverage as (
    select
        d.trade_date,
        count(distinct m.ticker) as expected_tickers,
        count(distinct p.ticker) as present_tickers
    from benchmark_days as d
    join members as m
        on m.added_date <= d.trade_date
        and d.trade_date < m.removed_before
        and m.listing_date <= d.trade_date
    left join {{ ref('stg_prices') }} as p
        on p.ticker = m.ticker and p.trade_date = d.trade_date
    group by d.trade_date
),

newest as (
    select max(trade_date) as newest_date from coverage
),

complete_days as (
    select c.trade_date
    from coverage as c
    cross join newest as n
    where c.present_tickers = c.expected_tickers
       or c.trade_date < n.newest_date
)

select
    trade_date,
    row_number() over (order by trade_date) as day_idx,
    min(trade_date) over () as cal_start
from complete_days
