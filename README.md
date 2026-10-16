# Market Bubble Early Warning System
BA882 Fall 2026 · Team 6 · Phase 1

Daily pipeline: yfinance → GCS → BigQuery → dbt → signal marts → dashboard.

## Lanes
| Lane | Owner | Folder |
|---|---|---|
| 1 Ingestion & orchestration | Kean | extractor/, dags/ |
| 2 Warehouse & dbt | | dbt/ |
| 3 Signal logic | Javier | dbt/ (marts) |
| 4 Dashboard | | dashboard/ |
| 5 Platform & PM | Chloe | terraform/, docs/ |

## Workflow
1. Create a branch: `git checkout -b lane1/extractor`
2. Commit and push the branch, then open a PR
3. One teammate approves, then merge. No direct pushes to main.

## Lane 1: running the extractor

Daily or any date range (safe to re-run; replaces those dates, never duplicates):

```
python extractor/extract.py --start 2026-10-01 --end 2026-10-09
```

**Backfill** (two years, ~3 min, ~11.7k rows):

```
python extractor/extract.py --start 2024-10-01 --end <today>
```

**Docker** (same image the DAG runs; credentials are passed in at run time, never baked in):

```
docker build -t lane1-extractor extractor/
docker run --rm lane1-extractor --start 2024-10-01 --end <today>
```
