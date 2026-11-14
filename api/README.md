# Model API (Phase 2)

Serves the latest weekly drawdown-probability scores (issue #89).

| Endpoint | Returns |
| --- | --- |
| `GET /risk?ticker=NVDA` | One stock: `prob_drop_20pct_60d`, `rank_in_universe`, `universe_size`, `in_our_basket`, `model_version`, today's `dial_level` and `dial_label` |
| `GET /basket` | Our 11 speculative stocks, highest probability first, plus the universe median |
| `GET /health` | Status and number of scored tickers |
| `GET /docs` | Interactive documentation (FastAPI) |

Every response includes `data_source`: `dummy` or `bigquery`.

## Status: skeleton on dummy data

Until `marts.model_scores` exists, the API serves `dummy_scores.csv` (20 made-up rows, `model_version = dummy-0`). **These numbers are not model output.** To switch to real scores (planned Nov 20):

1. Align the column names in `SCORES_SQL` (`main.py`) with schema contract v0.3.
2. Set `api_data_source = "bigquery"` in `terraform/variables.tf`, run `terraform plan`, open a PR, and apply after merge.

## Infrastructure

Defined in [terraform/api.tf](../terraform/api.tf): Cloud Run service `model-api` (us-east1, public, at most 2 instances) running as service account `model-api`, which can run queries and read the `marts` dataset only. Why public: see "Public model API" in [docs/decision_log.md](../docs/decision_log.md).

## Run locally

    cd api
    pip install -r requirements-dev.txt
    pytest -q
    uvicorn main:app --port 8080
    curl "localhost:8080/risk?ticker=NVDA"

## First deploy (Lane 5, Cloud Shell, after the MLflow deploy)

    gcloud builds submit api/ --tag us-east1-docker.pkg.dev/market-bubble-alert/mlops/model-api:0.1.0
    cd terraform
    terraform apply

The apply prints `model_api_url`. Test it:

    curl "$(cd terraform && terraform output -raw model_api_url)/risk?ticker=NVDA"

When the code changes, build with a new tag (for example `0.1.1`), update `local.api_image` in `terraform/api.tf`, and apply.
