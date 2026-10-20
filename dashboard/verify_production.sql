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
