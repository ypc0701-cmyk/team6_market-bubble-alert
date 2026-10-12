-- Structural invariants of the dial [M §3]: levels 3 and 4 only while armed; level 5 only on washout;
-- badges only at level 1 or an unarmed level 5; armed implies armed_since and quiet_days_used present;
-- breadth equals broken / valid.
select trade_date
from {{ ref('daily_signals') }}
where (dial_level in (3, 4) and not is_armed)
   or (dial_level = 5 and not cond_washout)
   or (cond_washout and dial_level <> 5)
   or (badge is not null and not (dial_level = 1 or (dial_level = 5 and not is_armed)))
   or (is_armed and (armed_since is null or quiet_days_used is null or armed_episode_id is null))
   or (not is_armed and (armed_since is not null or quiet_days_used is not null))
   or (spec_members_valid > 0 and abs(breadth - spec_members_broken / spec_members_valid) > 1e-6)
   or (is_held_today <> (divergence_run_days >= 15))
   or (is_quiet_day = (cond_deterioration or cond_repricing or cond_washout))
   or (is_armed and ((dial_level >= 3) = is_quiet_day))
