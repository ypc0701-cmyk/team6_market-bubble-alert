# Model API (Phase 2)

Serves the latest weekly drawdown-probability scores (issue #89).

| Endpoint | Returns |
| --- | --- |
| `GET /risk?ticker=NVDA` | One stock: every `model_scores` column in schema contract v0.3 (`prob_drop_20pct_60d`, `rank_in_universe`, `pct_rank_in_universe`, `prob_change_1w`, `role`, `model_name`, `model_version`, `trained_at`, ...), plus `in_our_basket` and today's `dial_level` and `dial_label` |
| `GET /basket` | Our speculative stocks (`role = our_basket`), highest probability first, plus the model version, universe size and median, and `missing_from_scores` (basket names without a score, e.g. SPCX until it has 126 trading days) |
| `GET /health` | Status and number of scored tickers |
| `GET /docs` | Interactive documentation (FastAPI) |

Every response includes `data_source`: `dummy` or `bigquery`.

## Status: skeleton on dummy data

Until `marts.model_scores` exists, the API serves `dummy_scores.csv`, a copy of the contract's dummy rows (`docs/dummy_rows/phase2/model_scores.csv`, `model_version = dummy-0`), latest week only. **These numbers are not model output.**

In bigquery mode the API reads the latest `as_of` of `marts.model_scores` (columns as in contract v0.3), the active speculative roster from `marts.basket_members`, and the latest dial from `marts.daily_signals`. To switch once `model_scores` is populated: set `api_data_source = "bigquery"` in `terraform/variables.tf`, run `terraform plan`, open a PR, and apply after merge.

## Infrastructure

Defined in [terraform/api.tf](../terraform/api.tf): Cloud Run service `model-api` (us-east1, public, at most 2 instances) running as service account `model-api`, which can run queries and read the `marts` dataset only. Why public: see "Public model API" in [docs/decision_log.md](../docs/decision_log.md).

## Alerts (issue #91)

`terraform/monitoring.tf` defines two alert policies from `docs/phase2_monitoring.md` section 4, each measured over about 24 hours:

- more than 1% of requests return 5xx
- p95 latency above 2 seconds (cold starts alone can trigger this when traffic is low, since the service scales to zero)

Alerts are emailed through a notification channel named **Lane 5 alerts**, created once by hand so no email address is stored in this public repo (Cloud Shell, before the first `terraform plan`):

    gcloud beta monitoring channels create --display-name="Lane 5 alerts" --type=email --channel-labels=email_address=YOUR_EMAIL@bu.edu

## Run locally

    cd api
    pip install -r requirements-dev.txt
    pytest -q
    uvicorn main:app --port 8080
    curl "localhost:8080/risk?ticker=NVDA"

## First deploy (Lane 5, Cloud Shell, after the MLflow deploy)

    gcloud builds submit api/ --tag us-east1-docker.pkg.dev/market-bubble-alert/mlops/model-api:0.2.0
    cd terraform
    terraform apply

The apply prints `model_api_url`. Test it:

    curl "$(cd terraform && terraform output -raw model_api_url)/risk?ticker=NVDA"

When the code changes, build with a new tag (for example `0.1.1`), update `local.api_image` in `terraform/api.tf`, and apply.
