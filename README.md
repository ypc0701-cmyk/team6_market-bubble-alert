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
