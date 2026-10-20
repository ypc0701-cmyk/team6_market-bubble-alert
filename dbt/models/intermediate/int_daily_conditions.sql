-- int_daily_conditions: the group math and the memoryless conditions of Methodology section 2,
-- one row per trading day. Shared by episodes and daily_signals (episodes needs cond_divergence
-- and breadth; daily_signals needs episodes), which is why it is split out. Ephemeral: it exists
-- only inside the two marts' compiled SQL. Carries a few helper columns (day_idx, is_close_day,
-- quiet_cum) that are not part of the contract.
{{ config(materialized='ephemeral') }}

with cal as (
    select * from {{ ref('int_trading_calendar') }}
),

dd as (
    select * from {{ ref('daily_drawdowns') }}
),

members as (
    select
        ticker,
        basket,
        listing_date,
        added_date,
        removed_date,
        coalesce(removed_date, date '9999-12-31') as removed_before
    from {{ ref('basket_members') }}
),

-- Speculative spans in force today, whether or not they have valid data [M §4].
in_force as (
    select
        c.trade_date,
        sum(case when m.basket = 'speculative' then 1 else 0 end) as spec_members_in_force,
        max(case when m.basket in ('speculative', 'megacap')
                  and (m.added_date = c.trade_date or m.removed_date = c.trade_date)
                 then 1 else 0 end) = 1 as roster_changed_today
    from cal as c
    left join members as m
        on m.added_date <= c.trade_date
        and c.trade_date < m.removed_before
        and m.listing_date <= c.trade_date
    group by c.trade_date
),

-- Valid members, ranked within (date, basket) so the median is the middle value or the mean of
-- the two middle values; exact and portable, no percentile function needed.
eligible as (
    select
        trade_date,
        basket,
        drawdown,
        is_broken,
        row_number() over (partition by trade_date, basket order by drawdown, ticker) as rn,
        count(*) over (partition by trade_date, basket) as cnt
    from dd
    where is_signal_eligible
),

basket_math as (
    select
        trade_date,
        basket,
        count(*) as members_valid,
        sum(case when is_broken then 1 else 0 end) as members_broken,
        avg(case when rn in (cast(floor((cnt + 1) / 2.0) as {{ dbt.type_int() }}), cast(floor((cnt + 2) / 2.0) as {{ dbt.type_int() }})) then drawdown end) as median_drawdown
    from eligible
    group by trade_date, basket
),

spx as (
    select trade_date, adj_close as spx_adj_close, reference_high as spx_reference_high, drawdown as spx_distance
    from dd
    where basket = 'benchmark'
),

conc_prices as (
    select trade_date, ticker, adj_close
    from {{ ref('stg_prices') }}
    where ticker in ('SPY', 'RSP')
),

concentration as (
    select
        c.trade_date,
        spy.adj_close / rsp.adj_close as concentration_ratio,
        max(spy.adj_close / rsp.adj_close) over (order by c.day_idx range between 125 preceding and current row) as concentration_high_126
    from cal as c
    join conc_prices as spy on spy.trade_date = c.trade_date and spy.ticker = 'SPY'
    join conc_prices as rsp on rsp.trade_date = c.trade_date and rsp.ticker = 'RSP'
),

arkk as (
    select trade_date, drawdown as arkk_drawdown
    from dd
    where ticker = 'ARKK'
),

assembled as (
    select
        c.trade_date,
        c.day_idx,
        coalesce(f.spec_members_in_force, 0) as spec_members_in_force,
        coalesce(s.members_valid, 0) as spec_members_valid,
        coalesce(s.members_broken, 0) as spec_members_broken,
        case when coalesce(s.members_valid, 0) > 0 then s.members_broken / s.members_valid end as breadth,
        s.median_drawdown as spec_median_drawdown,
        coalesce(f.roster_changed_today, false) as roster_changed_today,
        coalesce(m.members_valid, 0) as mega_members_valid,
        m.median_drawdown as mega_median_drawdown,
        x.spx_adj_close,
        x.spx_reference_high,
        x.spx_distance,
        k.concentration_ratio,
        k.concentration_high_126,
        k.concentration_ratio / k.concentration_high_126 - 1 as concentration_distance,
        k.concentration_ratio / k.concentration_high_126 - 1 <= -0.05 as is_concentration_broken,
        cr.credit_distance,
        cr.credit_status,
        a.arkk_drawdown
    from cal as c
    left join in_force as f on f.trade_date = c.trade_date
    left join basket_math as s on s.trade_date = c.trade_date and s.basket = 'speculative'
    left join basket_math as m on m.trade_date = c.trade_date and m.basket = 'megacap'
    join spx as x on x.trade_date = c.trade_date
    join concentration as k on k.trade_date = c.trade_date
    join {{ ref('credit_daily') }} as cr on cr.trade_date = c.trade_date
    left join arkk as a on a.trade_date = c.trade_date
),

conditions as (
    select
        *,
        coalesce(abs(arkk_drawdown - spec_median_drawdown) >= 0.15, false) as basket_audit_flag,
        -- Conditions [M §2 matrix]. A NULL breadth or median makes the divergence legs FALSE.
        coalesce(breadth >= 0.50 and spec_median_drawdown <= -0.15 and spx_distance > -0.05, false) as cond_divergence,
        coalesce(breadth >= 0.70 and spec_median_drawdown <= -0.25 and spx_distance > -0.05, false) as cond_divergence_strict,
        spx_distance <= -0.05 as det_spx_band,
        is_concentration_broken as det_concentration,
        credit_status = 'stress' as det_credit_stress,
        (spx_distance <= -0.05 or is_concentration_broken or credit_status = 'stress') as cond_deterioration,
        (spx_distance <= -0.10 and (coalesce(mega_median_drawdown <= -0.15, false) or is_concentration_broken)) as cond_repricing,
        (spx_distance <= -0.20 and coalesce(breadth >= 0.90, false) and credit_status = 'stress') as cond_washout,
        -- An episode closes on the first day breadth falls back below 30% [M §3].
        coalesce(breadth < 0.30, false) as is_close_day
    from assembled
),

runs as (
    select
        *,
        not (cond_deterioration or cond_repricing or cond_washout) as is_quiet_day,
        -- consecutive divergence days ending today: islands separated by non-divergence days
        sum(case when cond_divergence then 0 else 1 end) over (order by day_idx rows unbounded preceding) as run_grp
    from conditions
)

select
    *,
    case when cond_divergence
         then sum(case when cond_divergence then 1 else 0 end) over (partition by run_grp order by day_idx rows unbounded preceding)
         else 0 end as divergence_run_days,
    sum(case when is_quiet_day then 1 else 0 end) over (order by day_idx rows unbounded preceding) as quiet_cum
from runs
