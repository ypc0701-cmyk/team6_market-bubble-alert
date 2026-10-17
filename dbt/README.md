# Lane 2: Warehouse and dbt

## Overview

Lane 2 transforms raw market prices into clean, tested BigQuery data for Lane 3's signal calculations.

## Architecture

raw.prices_raw
    |
    v
staging.stg_prices
    |
    v
Lane 3 signal marts

The basket_members seed maintains the historical membership of the tracked stock baskets.

## Requirements

- Python 3.12
- dbt-core and dbt-bigquery
- Google Cloud CLI
- Access to GCP project: market-bubble-alert

## Local Setup

From the repository root:

1. Create and activate a Python environment:

   uv venv --python 3.12
   .\.venv\Scripts\Activate.ps1

2. Install dependencies:

   uv pip install dbt-bigquery

3. Navigate to dbt:

   cd dbt
   dbt deps

4. Configure a local ~/.dbt/profiles.yml with profile name ai_bubble_monitor, BigQuery OAuth authentication, project market-bubble-alert, location US, and target dev.

5. Authenticate:

   gcloud auth application-default login
   gcloud auth application-default set-quota-project market-bubble-alert

6. Verify:

   dbt debug

## Development Commands

Run from the dbt directory:

    dbt parse
    dbt source freshness
    dbt build --select stg_prices basket_members
    dbt docs generate
    dbt docs serve --port 8085 --host 127.0.0.1

## Dataset Naming

The generate_schema_name macro separates development and production.

| Target | Staging | Marts |
|---|---|---|
| dev | staging_dev | marts_dev |
| prod | staging | marts |

Production execution requires a separately configured prod target.

## Data Quality

The staging model validates required fields, unique ticker/date pairs, positive adjusted prices, and allowed providers.

The basket_members seed validates required metadata, accepted categories, unique membership keys, and non-overlapping membership periods.

A synthetic duplicate-record failure demonstration is preserved at docs/test_demos/test_duplicate_prices_demo.sql. It is intentionally excluded from normal dbt runs.

## Airflow Integration

Lane 1 operates the prices_daily DAG on Astronomer.

After ingestion, Airflow should execute dbt using the production target. The DAG must fail visibly if dbt models or tests fail.

Production deployment must occur from the merged main branch, coordinated with Lane 1.

## Validation

October 17, 2026:
- Raw data: 11,728 records across 24 tickers
- Staging model built successfully
- Basket seed: 24 records
- Development build: 22 passed, 0 warnings, 0 errors
- Source freshness passed
- Documentation catalog generated
- Synthetic duplicate-record test failed as expected
