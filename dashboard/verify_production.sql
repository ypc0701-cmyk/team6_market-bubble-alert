-- Read-only production checks. Run with BigQuery job location US.
SELECT table_name
FROM `market-bubble-alert.marts.INFORMATION_SCHEMA.TABLES`
WHERE table_name IN (
  'daily_signals', 'daily_drawdowns', 'credit_daily', 'episodes', 'basket_members'
)
ORDER BY table_name;

SELECT
  trade_date, dial_level, dial_label, badge, is_armed, armed_since,
  credit_status, spec_members_broken, spec_members_valid,
  basket_audit_flag, dial_explanation, computed_at
FROM `market-bubble-alert.marts.daily_signals`
ORDER BY trade_date DESC
LIMIT 1;

WITH latest AS (
  SELECT MAX(trade_date) AS trade_date
  FROM `market-bubble-alert.marts.daily_signals`
)
SELECT
  latest.trade_date,
  COUNT(d.ticker) AS priced_tickers,
  COUNTIF(d.basket = 'speculative') AS priced_speculative_tickers,
  MAX(d.computed_at) AS drawdowns_calculated_at
FROM latest
LEFT JOIN `market-bubble-alert.marts.daily_drawdowns` AS d
  ON d.trade_date = latest.trade_date
GROUP BY latest.trade_date;

-- Values displayed in the evidence and market-context panels.
SELECT
  trade_date, breadth, spec_median_drawdown, mega_median_drawdown,
  mega_members_valid, arkk_drawdown, credit_distance, concentration_distance,
  is_concentration_broken, divergence_run_days, quiet_days_used, armed_ceiling_date,
  cond_divergence, cond_divergence_strict, cond_deterioration,
  cond_repricing, cond_washout
FROM `market-bubble-alert.marts.daily_signals`
ORDER BY trade_date DESC
LIMIT 1;

SELECT
  episode_id, start_date, end_date, is_open, trading_days,
  max_divergence_run, is_held, held_date, disarm_date, computed_at
FROM `market-bubble-alert.marts.episodes`
WHERE start_date <= (
  SELECT MAX(trade_date) FROM `market-bubble-alert.marts.daily_signals`
)
ORDER BY start_date DESC
LIMIT 5;



-- The AI-specific qualifier requires a price for every active, listed roster symbol.
-- A missing drawdown for a priced young listing does not fail price coverage.
WITH latest AS (
  SELECT MAX(trade_date) AS trade_date
  FROM `market-bubble-alert.marts.daily_signals`
)
SELECT
  latest.trade_date,
  COUNT(*) AS active_listed_symbols,
  COUNTIF(d.adj_close IS NOT NULL) AS symbols_with_prices,
  COUNTIF(d.adj_close IS NULL) AS missing_prices,
  STRING_AGG(IF(d.adj_close IS NULL, m.ticker, NULL), ', ' ORDER BY m.ticker) AS missing_tickers
FROM latest
JOIN `market-bubble-alert.marts.basket_members` AS m
  ON m.added_date <= latest.trade_date
 AND (m.removed_date IS NULL OR latest.trade_date < m.removed_date)
 AND m.listing_date <= latest.trade_date
LEFT JOIN `market-bubble-alert.marts.daily_drawdowns` AS d
  ON d.trade_date = latest.trade_date
 AND d.ticker = m.ticker AND d.basket = m.basket
GROUP BY latest.trade_date;
