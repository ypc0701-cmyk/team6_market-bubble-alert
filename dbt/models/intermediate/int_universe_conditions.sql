-- int_universe_conditions (Lane 3, #83): the Phase 1 day-level conditions with the speculative leg
-- replaced by the Phase 2 universe. Everything that does not depend on the speculative basket (S&P,
-- megacap, concentration, credit, ARKK, det_* flags, cond_deterioration, cond_repricing) is read
-- unchanged from int_daily_conditions. Everything that does (breadth, median, cond_divergence,
-- cond_divergence_strict, cond_washout, close days, quiet days, run counts) is recomputed here with
-- the Phase 1 thresholds [M §2, M §3]. Column names keep the Phase 1 "spec_" prefix so episodes and
-- daily_signals logic runs unmodified on top; universe_dial_daily renames them.
{{ config(
    materialized='table',
    schema='intermediate',
    partition_by=({'field': 'trade_date', 'data_type': 'date'} if target.type == 'bigquery' else none)
) }}

with p1 as (
    select * from {{ ref('int_daily_conditions') }}
),

ud as (
    select * from {{ ref('int_universe_drawdowns') }}
),

members as (
    select
        ticker,
        listing_date,
        added_date,
        coalesce(removed_date, date '9999-12-31') as removed_before
    from {{ ref('universe_members') }}
),

in_force as (
    select
        p1.trade_date,
        count(m.ticker) as members_in_force
    from p1
    left join members as m
        on m.added_date <= p1.trade_date
        and p1.trade_date < m.removed_before
        and m.listing_date <= p1.trade_date
    group by p1.trade_date
),

-- Same exact median as Phase 1: the middle value, or the mean of the two middle values.
eligible as (
    select
        trade_date,
        drawdown,
        is_broken,
        row_number() over (partition by trade_date order by drawdown, ticker) as rn,
        count(*) over (partition by trade_date) as cnt
    from ud
    where is_signal_eligible
),

universe_math as (
    select
        trade_date,
        count(*) as members_valid,
        sum(case when is_broken then 1 else 0 end) as members_broken,
        avg(case when rn in (cast(floor((cnt + 1) / 2.0) as {{ dbt.type_int() }}), cast(floor((cnt + 2) / 2.0) as {{ dbt.type_int() }})) then drawdown end) as median_drawdown
    from eligible
    group by trade_date
),

assembled as (
    select
        p1.trade_date,
        p1.day_idx,
        coalesce(f.members_in_force, 0) as spec_members_in_force,
        coalesce(u.members_valid, 0) as spec_members_valid,
        coalesce(u.members_broken, 0) as spec_members_broken,
        case when coalesce(u.members_valid, 0) > 0 then u.members_broken / u.members_valid end as breadth,
        u.median_drawdown as spec_median_drawdown,
        p1.roster_changed_today,
        p1.mega_members_valid,
        p1.mega_median_drawdown,
        p1.spx_adj_close,
        p1.spx_reference_high,
        p1.spx_distance,
        p1.concentration_ratio,
        p1.concentration_high_126,
        p1.concentration_distance,
        p1.is_concentration_broken,
        p1.credit_distance,
        p1.credit_status,
        p1.arkk_drawdown,
        p1.det_spx_band,
        p1.det_concentration,
        p1.det_credit_stress,
        p1.cond_deterioration,
        p1.cond_repricing
    from p1
    left join in_force as f on f.trade_date = p1.trade_date
    left join universe_math as u on u.trade_date = p1.trade_date
),

conditions as (
    select
        *,
        coalesce(abs(arkk_drawdown - spec_median_drawdown) >= 0.15, false) as basket_audit_flag,
        coalesce(breadth >= 0.50 and spec_median_drawdown <= -0.15 and spx_distance > -0.05, false) as cond_divergence,
        coalesce(breadth >= 0.70 and spec_median_drawdown <= -0.25 and spx_distance > -0.05, false) as cond_divergence_strict,
        (spx_distance <= -0.20 and coalesce(breadth >= 0.90, false) and credit_status = 'stress') as cond_washout,
        coalesce(breadth < 0.30, false) as is_close_day
    from assembled
),

runs as (
    select
        *,
        not (cond_deterioration or cond_repricing or cond_washout) as is_quiet_day,
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
