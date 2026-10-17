-- reference_high and drawdown are NULL exactly while days_listed <= 20; is_mature is exactly days_listed >= 60;
-- is_broken agrees with drawdown. [M §2]
select trade_date, ticker
from {{ ref('daily_drawdowns') }}
where (days_listed <= 20 and (reference_high is not null or drawdown is not null or reference_window_days <> 0))
   or (days_listed >  20 and (reference_high is null or drawdown is null or reference_window_days = 0))
   or (is_mature <> (days_listed >= 60))
   or (drawdown is not null and is_broken <> (drawdown <= -0.25))
   or (drawdown is null and is_broken is not null)
   or (is_signal_eligible and (not is_mature or drawdown is null or basket not in ('speculative', 'megacap')))
