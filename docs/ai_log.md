# AI Use Log

| Date | Lane | Tool / Version | Purpose | Notes |
|---|---|---|---|---|
| 2026-10-11 | 5 | Claude | Summarized lane plan; repo setup walkthrough | |
| 2026-10-08 | 3 | Claude (Fable 5.1, Cowork) | Drafted schema contract v0.2, dbt YAML, singular tests, dummy rows from the Methodology; checked listing dates with yfinance 1.1.0 | Methodology and proposal written by Javier with Claude as editor |
| 2026-10-12 | 3 | Claude (Fable 5.1, Cowork) | Staged docs/ and dbt/ for this PR; drafted Lane 3 issues | |
| 2026-10-13 | 1 | Claude (Opus 5.5, claude.ai) | Wrote extractor/extract.py (yfinance to GCS to raw.prices_raw) against contract v0.2; ran and debugged in Cloud Shell | Output verified: 168 rows, no dupes on rerun |
| 2026-10-15 | 1 | Claude (Opus 5.5, claude.ai) | Ran 2-year backfill; wrote extractor/Dockerfile and README run section; tested image in Cloud Shell | 11,727 rows; docker run reloaded 3 days with no dupes |
| 2026-10-15 | 1 | Claude (Opus 5.5, claude.ai) | Added Tiingo fallback to extractor (per-ticker, --force-fallback and --dry-run flags); tested in Cloud Shell | Dry run: Tiingo served 23/24 tickers; ^GSPC not available on Tiingo |
| 2026-10-15 | 1 | Claude (Opus 5.5, claude.ai) | Wrote dags/prices_daily.py (Airflow 3), Astro project files, credential hook in extractor; validated DAG import in the Astro runtime image | DagBag: 0 import errors |
| 2026-10-16 | 1 | Claude (Opus 5.5, claude.ai) | Deployed DAG to Astronomer; slimmed image and pinned OpenTelemetry; force_fail param; Slack failure alert; weekday wake schedule; resolved README merge conflict | Scheduled + manual runs green; forced failure posted to #pipeline-alerts |
| 2026-10-17 | 2 | ChatGPT (GPT-6) | dbt setup, staging models, data quality tests, and documentation | Verified with 22 passing dbt checks |
| 2026-10-18 | 3 | Claude (Fable 5.1, Cowork) | Wrote the four mart models, two intermediates and the dial_explanation macro from the contract; synthetic seven-year scenario plus an independent Python oracle; dbt build in DuckDB and a cell-by-cell diff against the oracle; rebased onto Lane 2 staging with the partial-day rule | Materialization changed to full-rebuild tables; days_listed pre-backfill estimate documented in daily_drawdowns.sql |
| 2026-10-20 | 3 | Claude (Fable 5.1, Cowork) | Fixed roster_changed_today (removals undetectable, found in Ahrar's review); int_daily_conditions materialized as a table to stop BigQuery re-evaluating the ephemeral CTE; FORMAT in dial_explanation; added a ticker-removal case to the validation scenario and re-ran the oracle diff | |
