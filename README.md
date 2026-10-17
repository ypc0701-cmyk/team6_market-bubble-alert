# Market Bubble Early Warning System
BA882 Fall 2026 · Team 6 · Phase 1

Daily pipeline: yfinance → GCS → BigQuery → dbt → signal marts → dashboard.

## Lanes
| Lane | Owner | Folder |
|---|---|---|
| 1 Ingestion & orchestration | Kean | extractor/, dags/ |
| 2 Warehouse & dbt | Ahrar | dbt/ |
| 3 Signal logic | Javier | dbt/ (marts) |
| 4 Dashboard | Myhill | dashboard/ |
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
## GCP
- Project ID: `market-bubble-alert`
- Console: https://console.cloud.google.com/home/dashboard?project=market-bubble-alert
- Billing: budget alert at $50 (alerts at 50% / 90% / 100%)

### Resources (location: US)
| Resource | Name | Used by |
|---|---|---|
| GCS bucket | `gs://market-bubble-alert-landing` | Lane 1 |
| BigQuery dataset | `raw` | Lane 1 |
| BigQuery dataset | `staging` | Lane 2 |
| BigQuery dataset | `marts` | Lane 3 |
| Service account | `airflow-pipeline@market-bubble-alert.iam.gserviceaccount.com` | Airflow DAG |

Resources were created manually on Oct 11 to unblock Lane 1 and will be imported into Terraform.

### IAM
| Member | Lane | Roles |
|---|---|---|
| Kean | 1 | Viewer, BigQuery Job User, BigQuery Data Editor, Storage Object Admin, Artifact Registry Admin, Service Usage Consumer |
| Ahrar | 2 | Viewer, BigQuery Job User, BigQuery Data Editor, Service Usage Consumer |
| Javier | 3 | Viewer, BigQuery Job User, BigQuery Data Editor, Service Usage Consumer |
| Myhill | 4 | Viewer, BigQuery Job User, BigQuery Data Viewer, Service Usage Consumer |
| Chloe | 5 | Owner |
| airflow-pipeline (SA) | DAG | BigQuery Data Editor, BigQuery Job User, Storage Object Admin |

Service Usage Consumer was added on Oct 12: Python client libraries need it when running locally with user credentials.

### Local setup
cat >> docs/ai_log.md <<'EOF'
| 2026-10-11 | 5 | Claude | GitHub branch protection, labels, milestone and project board setup | |
| 2026-10-11 | 5 | Claude | GCP project, IAM, service account, bucket, datasets and budget alert setup | |
| 2026-10-12 | 5 | Claude | Diagnosed 403 on local API calls (missing Service Usage Consumer role) | |
| 2026-10-16 | 5 | Claude | Service account key handoff for Astronomer; README GCP docs | |
