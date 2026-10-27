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

## Lane 4: dashboard

Streamlit reads the signal marts and shows verdict cards, breadth versus S&P distance-from-high, dial history, member drawdowns, and a ticker table. See [dashboard setup and deployment](dashboard/README.md) for commands, data checks, and the demo handoff.

App URL: https://market-bubble-dashboard-roeklc77pq-ue.a.run.app (Cloud Run, public, no login required). Development uses `marts_dev`; the deployed app must use `marts`. Work is tracked in #50, #51, and #52.

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
| Service account | `dashboard-runtime@market-bubble-alert.iam.gserviceaccount.com` | Dashboard on Cloud Run |
| Cloud Run service | `market-bubble-dashboard` (us-east1) | Lane 4 |
| GCS bucket | `gs://market-bubble-alert-tfstate` (versioned) | Terraform state |

The landing bucket, the three datasets and `airflow-pipeline` were created by hand on Oct 11 to unblock Lane 1 and imported into Terraform on Oct 20 (see [terraform/README.md](terraform/README.md)). The dashboard service account, the Cloud Run service and the state bucket are managed by hand for Phase 1.

### IAM
| Member | Lane | Roles |
|---|---|---|
| Kean | 1 | Viewer, BigQuery Job User, BigQuery Data Editor, Storage Object Admin, Artifact Registry Admin, Service Usage Consumer |
| Ahrar | 2 | Viewer, BigQuery Job User, BigQuery Data Editor, Service Usage Consumer |
| Javier | 3 | Viewer, BigQuery Job User, BigQuery Data Editor, Service Usage Consumer |
| Myhill | 4 | Viewer, BigQuery Job User, BigQuery Data Viewer, Service Usage Consumer, Cloud Run Source Developer, Logs Viewer; Service Account User on `dashboard-runtime` and the Cloud Build service account |
| Chloe | 5 | Owner |
| airflow-pipeline (SA) | DAG | BigQuery Data Editor, BigQuery Job User, Storage Object Admin |
| dashboard-runtime (SA) | Dashboard | BigQuery Job User (project), BigQuery Data Viewer on `marts` only |
| Compute default SA (Cloud Build) | Build | Cloud Run Builder |

Service Usage Consumer was added on Oct 12: Python client libraries need it when running locally with user credentials.

The dashboard runs as its own service account, which can read `marts` and nothing else: no access to `raw` or `staging`, and no write access anywhere (least privilege; added Oct 20).

### Local setup

    gcloud auth login
    gcloud auth application-default login
    gcloud config set project market-bubble-alert

Service account keys are never committed to this repo. The Astronomer deployment authenticates with a key stored as an Astronomer connection.
