# Lane 4 dashboard

Streamlit displays the dbt marts. The app does not calculate drawdowns, returns, breadth, arming, or dial levels.

## Run in Cloud Shell or locally

From the repository root:

```bash
python -m venv .venv-dashboard
source .venv-dashboard/bin/activate
python -m pip install -r dashboard/requirements.txt
```

Use your existing working Google credentials. For a local setup that needs ADC:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project market-bubble-alert
```

Development:

```bash
GCP_PROJECT=market-bubble-alert BQ_DATASET=marts_dev \
  python -m streamlit run dashboard/app.py \
  --server.address=0.0.0.0 --server.port=8080
```

Open Cloud Shell Web Preview on port 8080.

Production, after the production tables have been built:

```bash
GCP_PROJECT=market-bubble-alert BQ_DATASET=marts \
  python -m streamlit run dashboard/app.py \
  --server.address=0.0.0.0 --server.port=8080
```

The app keeps the selected dataset explicit. A production query error remains visible; it does not switch to development data.

| Setting | Default | Meaning |
|---|---|---|
| GCP_PROJECT | market-bubble-alert | Query and billing project |
| BQ_DATASET | marts_dev | Allowed values: marts_dev, marts |
| BQ_LOCATION | US | BigQuery job location |
| PORT | 8080 in the container | Cloud Run listening port |

Dependencies are separate from the Airflow project's root requirements.

## Data used

| View | Source |
|---|---|
| Verdict, explanation, badge, credit, history | daily_signals |
| Drawdown and six-month return | daily_drawdowns |
| Company names and active membership | basket_members |

The verdict uses the latest date available in daily_signals. The member query uses that exact date as a DATE parameter and joins the membership span in force on that date. A missing member price stays visible as N/A. The company name is metadata; every analytical measure comes from dbt.

The chart filter changes the historical display, not the latest verdict. Arming and roster changes from daily_signals are marked on the dial history. The member table is sorted by drawdown, worst first, with missing values last.

The open page checks every 60 seconds. Cached warehouse results expire after 60 seconds. Refresh data clears both caches. The dashboard does not run ingestion or dbt.

### Freshness and limitations

The page displays the trading date, calculation time in UTC, and last check time. It warns when:
- the calculation time is missing or older than 72 hours;
- the trading date is at least two weekdays behind the expected evening update.

The date check allows updates until 7pm America/New_York and excludes weekends. It is a display heuristic: US exchange holidays can cause warnings, and this is not proof of DAG health or a substitute for Lane 2 source freshness tests.

Badges are displayed from the mart. A basket-audit flag shows the ARKK disagreement warning. The final AI-specific qualifier still needs Lane 3 wording confirmation; the app currently asks the reader to review basket construction before using a reading market-wide.

## Verify production data

Run this read-only script from the repository root:

```bash
bq query --project_id=market-bubble-alert --location=US \
  --use_legacy_sql=false < dashboard/verify_production.sql
```

Confirm that all five tables are listed and the latest signal date and fields match the production page. The per-ticker summary uses that same signal date. Keep the output with the integration notes.

The scheduled production build is tracked in PR #48. Once merged and deployed by Lane 1, it should run dbt build --target prod after ingestion. Confirm a successful real run; a merged PR alone does not establish the state of the warehouse.

## Tests without GCP

```bash
python -m pip install -r dashboard/requirements-dev.txt
python -m pytest dashboard/tests -q
```

The tests mock BigQuery with the repository's dummy rows. They cover six dial levels, both badges, unarmed and roster events, null prices and returns, empty and failed queries, stale results, and production dataset selection. They validate the UI, not the signal algorithm or production credentials.

## Cloud Run deployment

Deployment status: pending. Add the verified team URL to the root README after deployment.

Coordinate these setup items with Chloe:
- Enable Cloud Run, Cloud Build, and Artifact Registry APIs.
- Configure the deployment and build permissions.
- Create or select a dedicated dashboard runtime service account.
- Give that runtime identity BigQuery Job User on the project and BigQuery Data Viewer on the marts dataset.
- Configure team browser access with IAP and grant the selected team accounts access.

The application uses ADC. Cloud Run supplies its attached runtime identity; no downloaded service-account key belongs in the image.

After the PR is reviewed and merged, deploy the dashboard folder from main. Set DASHBOARD_SERVICE_ACCOUNT to the actual runtime account Chloe configured:

```bash
export DASHBOARD_SERVICE_ACCOUNT="REPLACE_WITH_CONFIRMED_SERVICE_ACCOUNT_EMAIL"

gcloud run deploy market-bubble-dashboard \
  --project=market-bubble-alert \
  --region=us-east1 \
  --source=dashboard \
  --service-account="$DASHBOARD_SERVICE_ACCOUNT" \
  --set-env-vars=GCP_PROJECT=market-bubble-alert,BQ_DATASET=marts,BQ_LOCATION=US \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=2 \
  --timeout=3600 \
  --no-allow-unauthenticated
```

The dashboard Dockerfile is separate from the root Astronomer Dockerfile. Only the app and requirements are uploaded and copied into its build context.

For team browser access, Chloe can open the service's Security tab, choose Require authentication and Identity-Aware Proxy (IAP), and grant team access. First-time OAuth setup depends on the project's organization. Confirm login and Streamlit interactions from a teammate's browser before marking deployment complete.

Retrieve the service URL:

```bash
gcloud run services describe market-bubble-dashboard \
  --project=market-bubble-alert --region=us-east1 \
  --format='value(status.url)'
```

A service URL must be tested with the configured access policy. Include the confirmed URL and access instructions in the root README.

Official references:
- [Streamlit on Cloud Run](https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-streamlit-service)
- [Cloud Run service identity](https://docs.cloud.google.com/run/docs/securing/service-identity)
- [IAP for Cloud Run](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)

## Demo handoff

1. Confirm the displayed dataset is marts and compare the verdict with the SQL output.
2. Explain the dial, explanation, credit, badge, and armed-since date.
3. Show breadth versus the S&P, dial history, and one member drawdown and six-month return.
4. Explain any basket-audit or stale-data warning.
5. After a successful upstream production build, confirm a later page check reflects the new mart results.
6. Give Lane 5 the tested URL, screenshots, and a short walkthrough for the rehearsal and fallback video.

Track remaining work in #50, #51, and #52. Live production verification, final audit wording, Cloud Run access, and the demo handoff remain open.
