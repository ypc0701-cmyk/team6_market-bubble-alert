-- DEMONSTRATION TEST: Intentionally fails on duplicate records.
-- Uses synthetic data only. Does not read or modify production tables.

WITH sample_prices AS (
    SELECT DATE '2026-10-15' AS trade_date, 'NVDA' AS ticker, 180.50 AS adj_close
    UNION ALL
    SELECT DATE '2026-10-15', 'MSFT', 520.00
    UNION ALL
    SELECT DATE '2026-10-15', 'NVDA', 180.50
)

SELECT
    trade_date,
    ticker,
    COUNT(*) AS duplicate_count
FROM sample_prices
GROUP BY trade_date, ticker
HAVING COUNT(*) > 1
