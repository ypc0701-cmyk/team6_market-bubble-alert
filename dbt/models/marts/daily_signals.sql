-- daily_signals: the group math, the conditions, the memory and the dial of Methodology sections 2
-- and 3, one row per trading day [M §2, M §3, M §6, L4]. "The dial level for today is queryable
-- with one SELECT" means this table; the dashboard performs no logic.
{{ config(
    materialized='table',
    partition_by=({'field': 'trade_date', 'data_type': 'date'} if target.type == 'bigquery' else none)
) }}

with c as (
    select * from {{ ref('int_daily_conditions') }}
),

ep as (
    select * from {{ ref('episodes') }}
),

-- Arming intervals [held_date, disarm_date) that cover today; the most recent one wins [M §3].
arming as (
    select
        c.trade_date,
        e.episode_id,
        e.start_date,
        e.held_date,
        e.armed_ceiling_date,
        cs.quiet_cum - (case when cs.is_quiet_day then 1 else 0 end) as quiet_base,
        row_number() over (partition by c.trade_date order by e.held_date desc) as rn
    from c
    join ep as e
        on e.is_held
        and e.held_date <= c.trade_date
        and c.trade_date < coalesce(e.disarm_date, date '9999-12-31')
    join c as cs on cs.trade_date = e.start_date
),

armed_today as (
    select * from arming where rn = 1
),

-- The span covering today (open on that day), for the dashboard's annotation.
covering as (
    select c.trade_date, e.episode_id
    from c
    join ep as e on e.start_date <= c.trade_date and (e.end_date is null or c.trade_date <= e.end_date)
),

held_today as (
    select held_date as trade_date, max(episode_id) as episode_id from ep where is_held group by held_date
),

disarmed_today as (
    select disarm_date as trade_date, max(disarm_reason) as disarm_reason from ep where disarm_date is not null group by disarm_date
),

memory as (
    select
        c.*,
        a.episode_id is not null as is_armed,
        a.start_date as armed_since,
        a.episode_id as armed_episode_id,
        case when a.episode_id is not null
             then least(378, c.quiet_cum - a.quiet_base) end as quiet_days_used,
        a.armed_ceiling_date,
        cv.episode_id as episode_id,
        h.episode_id is not null as held_event_today,
        d.disarm_reason
    from c
    left join armed_today as a on a.trade_date = c.trade_date
    left join covering as cv on cv.trade_date = c.trade_date
    left join held_today as h on h.trade_date = c.trade_date
    left join disarmed_today as d on d.trade_date = c.trade_date
),

events as (
    select
        *,
        coalesce(lag(is_armed) over (order by day_idx), false) as was_armed_yesterday
    from memory
),

dial as (
    select
        *,
        case
            when held_event_today and not was_armed_yesterday then 'armed'
            when held_event_today and was_armed_yesterday then 'rearmed'
            when not is_armed and was_armed_yesterday and disarm_reason = 'quiet_expiry' then 'disarmed_quiet'
            when not is_armed and was_armed_yesterday and disarm_reason = 'ceiling' then 'disarmed_ceiling'
        end as armed_state_change,
        -- The dial, top down [M §3]
        case
            when cond_washout then 5
            when is_armed and cond_repricing then 4
            when is_armed and cond_deterioration then 3
            when is_armed and spx_distance > -0.05 then 2
            when cond_divergence or credit_status in ('watch', 'stress') or is_armed or cond_deterioration or cond_repricing then 1
            else 0
        end as dial_level,
        -- Badges qualify an unarmed reading; off_pattern wins ties [M §3]
        case
            when not is_armed and (det_spx_band or det_concentration or cond_repricing or cond_washout) then 'off_pattern'
            when not is_armed and credit_status = 'stress' then 'credit_only'
        end as badge
    from events
),

labelled as (
    select
        *,
        case dial_level
            when 0 then 'CALM'
            when 1 then 'STRAIN'
            when 2 then 'DIVERGENCE'
            when 3 then 'TOPPING'
            when 4 then 'REPRICING'
            when 5 then 'WASHOUT'
        end as dial_label
    from dial
)

select
    trade_date,
    spec_members_in_force,
    spec_members_valid,
    spec_members_broken,
    breadth,
    spec_median_drawdown,
    roster_changed_today,
    mega_members_valid,
    mega_median_drawdown,
    spx_adj_close,
    spx_reference_high,
    spx_distance,
    concentration_ratio,
    concentration_high_126,
    concentration_distance,
    is_concentration_broken,
    credit_distance,
    credit_status,
    arkk_drawdown,
    basket_audit_flag,
    cond_divergence,
    cond_divergence_strict,
    det_spx_band,
    det_concentration,
    det_credit_stress,
    cond_deterioration,
    cond_repricing,
    cond_washout,
    divergence_run_days,
    divergence_run_days >= 15 as is_held_today,
    episode_id,
    is_quiet_day,
    is_armed,
    armed_since,
    armed_episode_id,
    quiet_days_used,
    armed_ceiling_date,
    armed_state_change,
    dial_level,
    dial_label,
    badge,
    {{ dial_explanation() }} as dial_explanation,
    {{ dbt.current_timestamp() }} as computed_at
from labelled
