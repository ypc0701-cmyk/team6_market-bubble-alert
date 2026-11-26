-- universe_dial_daily (Lane 3, #83; contract v0.3): the Phase 1 dial with the speculative leg computed
-- on the Phase 2 universe instead of our 11. Megacap, S&P, concentration and credit legs are the
-- Phase 1 values unchanged (they come through int_universe_conditions from int_daily_conditions).
-- Generated from marts/daily_signals.sql with only the inputs and the final column list changed, so
-- the memory (arming, quiet expiry, ceiling) and the top-down dial rule are identical to Phase 1.
-- The official dial is copied next to it: "how does the dial read on the bigger basket" is one SELECT.
{{ config(
    materialized='table',
    partition_by=({'field': 'trade_date', 'data_type': 'date'} if target.type == 'bigquery' else none)
) }}

with c as (
    select * from {{ ref('int_universe_conditions') }}
),

ep as (
    select * from {{ ref('int_universe_episodes') }}
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
    l.trade_date,
    l.spec_members_valid as univ_members_valid,
    l.spec_members_broken as univ_members_broken,
    l.breadth as universe_breadth,
    l.spec_median_drawdown as universe_median_drawdown,
    l.cond_divergence,
    l.is_armed,
    l.armed_since,
    l.dial_level as universe_dial_level,
    l.dial_label as universe_dial_label,
    o.dial_level as official_dial_level,
    l.dial_level = o.dial_level as dials_agree,
    {{ dbt.current_timestamp() }} as computed_at
from labelled as l
join {{ ref('daily_signals') }} as o on o.trade_date = l.trade_date
