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
  --server.address=0.0.0.0 \
  --server.port=8081 \
  --browser.serverAddress="8081-${WEB_HOST}" \
  --browser.serverPort=443 \
  --browser.gatherUsageStats=false
```

Open Cloud Shell Web Preview on port 8081.

Production data in Cloud Shell:

```bash
GCP_PROJECT=market-bubble-alert BQ_DATASET=marts BQ_LOCATION=US \
python -m streamlit run dashboard/app.py \
  --server.address=0.0.0.0 \
  --server.port=8081 \
  --browser.serverAddress="8081-${WEB_HOST}" \
  --browser.serverPort=443 \
  --browser.gatherUsageStats=false
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
| Signal evidence, basket medians, credit and concentration trends | daily_signals |
| Drawdown and six-month return | daily_drawdowns |
| Company names and active membership | basket_members |
| Divergence spans and confirmation/disarming dates | episodes |

The verdict uses the latest date available in daily_signals. The member query uses that exact date as a DATE parameter and joins the membership span in force on that date. A missing member price stays visible as N/A. The company name is metadata; every analytical measure comes from dbt.

The chart filter changes the historical display, not the latest verdict. Arming and roster changes from daily_signals are marked on the dial history. The member table is sorted by drawdown, worst first, with missing values last.

### Additional views

- Signal evidence shows speculative breadth, the speculative median drawdown, S&P distance from high and credit-ratio distance. Today's condition flags and the armed-clock fields come directly from daily_signals. They explain the verdict without calculating a new signal in the app.
- Basket comparison puts the speculative and megacap medians next to ARKK's drawdown. ARKK is one reference ETF, not a basket median or a dial input. Eligible-member counts and missing values stay explicit.
- Credit and concentration plots use HYG / IEF and SPY / RSP distances from their own 126-trading-day highs. The History selector changes these plots along with the existing trend charts.
- Episode history reads the current episodes mart. Its start-date query is parameterized with the latest signal date; the aggregate span records reflect the current episode build and are not a historical snapshot controlled by History. Open or unconfirmed dates stay empty. A closed episode does not necessarily mean that the armed clock has expired.

The Members selector changes only the member chart and table. The global verdict and speculative broken/eligible count keep their meaning when megacap is selected.

The open page checks every 60 seconds. Cached warehouse results expire after 60 seconds. Refresh data clears the signal, member and episode caches. An unavailable episode query shows a separate error while the verdict and other available views remain visible. The dashboard does not run ingestion or dbt.

### Freshness and limitations

The page displays the trading date, calculation time in UTC, and last check time. It warns when:
- the calculation time is missing or older than 72 hours;
- the trading date is at least two weekdays behind the expected evening update.

The date check allows updates until 7pm America/New_York and excludes weekends. It is a display heuristic: US exchange holidays can cause warnings, and this is not proof of DAG health or a substitute for Lane 2 source freshness tests.

Badges are displayed from the mart. A basket-audit flag shows the ARKK disagreement warning. Methodology section 4, merged in PR #61, defines the AI-specific qualifier. When basket_audit_flag is true and every active, listed roster symbol has a price on the verdict date, the app displays: "AI-specific: the broader speculative market (ARKK) does not confirm this break." The coverage check includes the benchmark and reference series. It uses adjusted-close availability, so a priced young listing with no usable drawdown does not count as a missing price. Incomplete, empty or failed member reads retain the audit warning. The app does not change the dial, badge or armed state.

## Verify production data

Run this read-only script from the repository root:

```bash
bq query --project_id=market-bubble-alert --location=US \
  --use_legacy_sql=false < dashboard/verify_production.sql
```

Confirm that all five tables are listed and the latest signal date and fields match the production page. The per-ticker summary uses that same signal date. Keep the output with the integration notes.

Production data reads were verified in Cloud Shell on 2026-10-20. The captured page shows `market-bubble-alert.marts`, a signal date of 2026-10-19, and a calculation time of 2026-10-20 19:55 UTC. The verdict is Level 2 DIVERGENCE, credit is normal, and 10 of 11 eligible speculative names are broken. This verifies the production UI connection; the SQL output should also be retained for the integration record.

PR #48 (dbt after ingestion) and PR #54 (roster fix and faster builds) are merged. Lane 3 reports a rebuild from main passing 121/121 in under two minutes. Issue #44 records that Lane 1 redeployed main including #59 and confirmed both extract_and_load and dbt_build succeeded. That upstream integration is complete. The enhanced Cloud Run revision still needs a retained UI-versus-SQL check after deployment.

## Tests without GCP

```bash
python -m pip install -r dashboard/requirements-dev.txt
python -m pytest dashboard/tests -q
```

The tests mock BigQuery with the repository's dummy rows. They cover six dial levels, both badges, unarmed and roster events, null prices and returns, empty and failed queries, stale results, production dataset selection, evidence values, episode dates, member switching and refresh of all three caches. They also check full-roster price coverage, the AI-specific qualifier with young listings, and warning fallback on missing or failed price reads. The closeout run passed 29 checks. They validate the UI, not the signal algorithm or production credentials.

## Cloud Run deployment

The original release is deployed at https://market-bubble-dashboard-41316181588.us-east1.run.app. Teammates confirmed browser access and interaction on 2026-10-20. PR #60 (the additional views), PR #58 (URL and IAM documentation), and PR #61 (methodology wording) are merged. The additional views and the qualifier follow-up still need a recorded check of the deployed Cloud Run revision. A Cloud Shell preview reading production marts is not proof that the Cloud Run revision has been updated.

Coordinate these setup items with Chloe:
- Enable Cloud Run, Cloud Build, and Artifact Registry APIs.
- Configure the deployment and build permissions.
- Create or select a dedicated dashboard runtime service account.
- Give that runtime identity BigQuery Job User on the project and BigQuery Data Viewer on the marts dataset.
- Configure team browser access with IAP and grant the selected team accounts access.

The application uses ADC. Cloud Run supplies its attached runtime identity; no downloaded service-account key belongs in the image.

After the qualifier follow-up is reviewed and merged, deploy the dashboard folder from main. Set DASHBOARD_SERVICE_ACCOUNT to the actual runtime account Chloe configured:

```bash
export DASHBOARD_SERVICE_ACCOUNT="dashboard-runtime@market-bubble-alert.iam.gserviceaccount.com"

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

Track remaining work in #51 and #52; #50 is complete. The original release's production reads and team interaction are verified on Cloud Run. The additional views need a live production check after redeployment. The remaining release evidence and the issue-closing criteria are tracked in [Lane 4 handoff](../docs/lane4_handoff.md).
