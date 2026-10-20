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
| 2026-10-19 | 1 | Claude (Opus 5.5, claude.ai) | Added dbt_build task (dbt build --target prod) after extract_and_load; dbt 1.12 in its own venv in the Astro image; validated project parse with lane3/marts merged | Parse OK, models resolve to staging/marts on prod target |
