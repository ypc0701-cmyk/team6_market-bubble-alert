-- episodes: the receipts behind armed [M §3, M §6]. One row per contiguous divergence span.
-- A span begins on the first trading day cond_divergence is TRUE and ends on the first later day on
-- which breadth < 0.30 (that day is excluded). Days inside the span on which the condition is FALSE
-- but breadth stays >= 0.30 remain in it. Rebuilt in full each run because an open span changes daily.
--
-- The armed clock without a state machine [contract §3]: quiet days are memoryless, so the 378th
-- quiet day after armed_since is a window count (quiet_cum), each held span gets a fixed arming
-- interval [held_date, disarm_date), and daily_signals asks "does some interval cover today".
{{ config(
    materialized='table',
    partition_by=({'field': 'start_date', 'data_type': 'date'} if target.type == 'bigquery' else none)
) }}

with c as (
    select * from {{ ref('int_daily_conditions') }}
),

-- Segments are delimited by close days: each close day starts a new segment (it belongs to no span).
segmented as (
    select
        *,
        sum(case when is_close_day then 1 else 0 end) over (order by day_idx rows unbounded preceding) as seg_id
    from c
),

bounds as (
    select max(seg_id) as last_seg_id from segmented
),

-- A span starts at the first divergence day inside its segment and runs to the end of the segment.
starts as (
    select seg_id, min(day_idx) as start_idx, min(trade_date) as start_date
    from segmented
    where cond_divergence
    group by seg_id
),

span_days as (
    select s.*, st.start_date
    from segmented as s
    join starts as st on st.seg_id = s.seg_id and s.day_idx >= st.start_idx
),

spans as (
    select
        start_date,
        seg_id,
        max(trade_date) as last_date,
        count(*) as trading_days,
        sum(case when cond_divergence then 1 else 0 end) as divergence_days,
        max(divergence_run_days) as max_divergence_run,
        min(case when divergence_run_days >= 15 then trade_date end) as held_date,
        max(breadth) as max_breadth,
        min(spec_median_drawdown) as min_spec_median_drawdown,
        sum(case when cond_divergence_strict then 1 else 0 end) as strict_days
    from span_days
    group by start_date, seg_id
),

-- quiet_cum on the day before armed_since, so quiet_cum - quiet_base counts quiet days from
-- armed_since inclusive.
armed as (
    select
        sp.*,
        case when sp.max_divergence_run >= 15 then sp.start_date end as armed_since,
        cs.quiet_cum - (case when cs.is_quiet_day then 1 else 0 end) as quiet_base
    from spans as sp
    join c as cs on cs.trade_date = sp.start_date
),

expiry as (
    select
        a.start_date,
        min(case when q.quiet_cum - a.quiet_base >= 378 then q.trade_date end) as quiet_expiry_date
    from armed as a
    join c as q on q.trade_date >= a.start_date
    where a.armed_since is not null
    group by a.start_date
),

with_dates as (
    select
        a.*,
        case when a.armed_since is not null
             then cast({{ dbt.dateadd('month', 36, 'a.armed_since') }} as date) end as armed_ceiling_date,
        e.quiet_expiry_date
    from armed as a
    left join expiry as e on e.start_date = a.start_date
),

-- The first trading day after the quiet expiry, and the first trading day on or after the ceiling.
-- NULL while that day has not happened yet.
disarm_candidates as (
    select
        w.start_date,
        min(case when q.trade_date > w.quiet_expiry_date then q.trade_date end) as quiet_disarm_date,
        min(case when q.trade_date >= w.armed_ceiling_date then q.trade_date end) as ceiling_disarm_date
    from with_dates as w
    cross join c as q
    where w.armed_since is not null
    group by w.start_date
),

candidates as (
    select w.*, dc.quiet_disarm_date, dc.ceiling_disarm_date, b.last_seg_id
    from with_dates as w
    left join disarm_candidates as dc on dc.start_date = w.start_date
    cross join bounds as b
)

select
    concat('EP-', cast(start_date as {{ dbt.type_string() }})) as episode_id,
    start_date,
    case when seg_id = last_seg_id then null else last_date end as end_date,
    seg_id = last_seg_id as is_open,
    trading_days,
    divergence_days,
    max_divergence_run,
    max_divergence_run >= 15 as is_held,
    held_date,
    max_breadth,
    min_spec_median_drawdown,
    strict_days,
    armed_since,
    armed_ceiling_date,
    quiet_expiry_date,
    case
        when quiet_disarm_date is not null and (ceiling_disarm_date is null or quiet_disarm_date <= ceiling_disarm_date) then quiet_disarm_date
        else ceiling_disarm_date
    end as disarm_date,
    case
        when quiet_disarm_date is not null and (ceiling_disarm_date is null or quiet_disarm_date <= ceiling_disarm_date) then 'quiet_expiry'
        when ceiling_disarm_date is not null then 'ceiling'
    end as disarm_reason,
    {{ dbt.current_timestamp() }} as computed_at
from candidates
