# AI Use Log

| Date | Lane | Tool / Version | Purpose | Notes |
|---|---|---|---|---|
| 2026-10-11 | 5 | Claude | Summarized lane plan; repo setup walkthrough | |
| 2026-10-08 | 3 | Claude (Fable 5.1, Cowork) | Drafted schema contract v0.2, dbt YAML, singular tests, dummy rows from the Methodology; checked listing dates with yfinance 1.1.0 | Methodology and proposal written by Javier with Claude as editor |
| 2026-10-12 | 3 | Claude (Fable 5.1, Cowork) | Staged docs/ and dbt/ for this PR; drafted Lane 3 issues | |
| 2026-10-13 | 1 | Claude (Opus 5.5, claude.ai) | Wrote extractor/extract.py (yfinance to GCS to raw.prices_raw) against contract v0.2; ran and debugged in Cloud Shell | Output verified: 168 rows, no dupes on rerun |
