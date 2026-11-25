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

Streamlit reads the signal marts and shows verdict cards, signal evidence, breadth versus S&P distance, dial history, basket comparison, credit and concentration trends, member drawdowns and returns, and episode history. Signal calculations stay in dbt.

Team URL: https://market-bubble-dashboard-41316181588.us-east1.run.app (Cloud Run, public, no login required). The original Cloud Run release and team access were verified on Oct 20. PR #60 is merged; the enhanced revision and qualifier follow-up still need recorded Cloud Run production verification. Development uses marts_dev and production uses marts.

See [dashboard setup](dashboard/README.md) and [Lane 4 handoff](docs/lane4_handoff.md). #50 is complete; close #51 and #52 only after their remaining acceptance criteria have evidence.

## Lane 1: running the extractor

**Which tickers.** Every run loads the union of `marts.basket_members` (the 24 Phase 1 symbols) and `marts.universe_members` (the Phase 2 universe), duplicates dropped: 24 + 141 - 7 overlaps = **158** as of Nov 25, 2026. Nobody edits a list in the code.

**Re-runs are safe.** A run deletes only the (date, ticker) pairs it is loading, then appends. Re-running a range never duplicates rows, and loading one ticker never touches any other ticker's rows.

Daily or any date range:

```
python extractor/extract.py --start 2026-11-16 --end 2026-11-20
```

Add `--dry-run` to fetch and print counts without writing anything.

**Full backfill** (what ran on Nov 25, 2026: ~15 min, 246,237 rows, 158 tickers, 1,734 trading days):

```
python extractor/extract.py --start 2020-01-01 --end <today> --run-id backfill-2020
```

Note: the dial uses `adj_close`, and Yahoo re-adjusts past prices whenever a dividend is paid. A full re-pull can therefore move old drawdowns in the 3rd or 4th decimal for dividend payers (HYG and IEF the most). On Nov 25 that flipped `credit_status` on 3 days that sat on the -3% line; no dial level changed (see #70).

### Backfill one new universe ticker

When Lane 3 adds a name (say `ABCD`) to `universe_members`:

1. Lane 2 merges the seed change, and Lane 1 redeploys Astronomer so `dbt seed` puts the new row in `marts.universe_members`.
2. Load its history (only `ABCD` is deleted and reloaded; every other ticker is untouched):
   ```
   python extractor/extract.py --tickers ABCD --start 2020-01-01 --end <today> --run-id backfill-ABCD
   ```
3. Check it landed:
   ```
   bq query --use_legacy_sql=false 'SELECT COUNT(*) n, MIN(trade_date) first, MAX(trade_date) last FROM raw.prices_raw WHERE ticker="ABCD"'
   ```
   `first` should be Jan 2, 2020, or the listing date if later.

Load prices only for tickers that are already in `basket_members` or `universe_members`: the `prices_raw.ticker` test fails `dbt build` on anything else.

### Refreshing the universe (manual, never automatic)

The universe changes only when Lane 3 decides it should, never on a schedule:

1. Lane 3 re-pulls ETF holdings and rebuilds the list: `python scripts/build_universe_snapshot.py`, writing a new dated folder under `docs/universe_snapshot_<date>/`, and opens a PR.
2. Lane 2 updates `dbt/seeds/universe_members.csv` from it. **Names that leave get a `removed_date` and `removed_reason`; rows are never deleted**, so their loaded prices still pass the `prices_raw.ticker` test.
3. Lane 1 redeploys Astronomer, then backfills only the new names with `--tickers NEW1,NEW2` as above.

**Docker** (same image the DAG runs; credentials are passed in at run time, never baked in):

```
docker build -t lane1-extractor extractor/
docker run --rm lane1-extractor --start 2026-11-16 --end 2026-11-20
```

**Deploying to Astronomer** (Cloud Shell): wake it first, and only ever deploy from `main`.

```
astro deployment wake-up cmv1bvgol448o01plig8o0pqs --for 3h -f
echo '{"max-concurrent-uploads": 1}' | sudo tee /etc/docker/daemon.json && sudo service docker restart
astro deploy cmv1bvgol448o01plig8o0pqs -f
```

The upload-limit line is needed after every Cloud Shell reset; without it the image push stalls. If the push still hangs or returns 503/403: `docker logout cliemx7ny00uu01mbf12mk2gu.registry.astronomer.run` and deploy again.

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
