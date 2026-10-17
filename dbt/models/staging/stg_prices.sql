{{ config(materialized='view') }}

SELECT
    CAST(trade_date AS DATE) AS trade_date,
    UPPER(TRIM(ticker)) AS ticker,
    CAST(open AS FLOAT64) AS open,
    CAST(high AS FLOAT64) AS high,
    CAST(low AS FLOAT64) AS low,
    CAST(close AS FLOAT64) AS close,
    CAST(adj_close AS FLOAT64) AS adj_close,
    CAST(volume AS INT64) AS volume,
    source,
    CAST(ingested_at AS TIMESTAMP) AS ingested_at,
    run_id
FROM {{ source('raw', 'prices_raw') }}
