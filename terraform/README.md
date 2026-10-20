# Terraform

Manages the core GCP resources for `market-bubble-alert`:
- GCS bucket `market-bubble-alert-landing`
- BigQuery datasets `raw`, `staging`, `marts`
- Service account `airflow-pipeline`

These were created by hand on Oct 11 so Lane 1 was not blocked, then imported with
the `import` blocks in `imports.tf`. IAM role bindings are still managed by hand
(see the IAM table in the root README) and are a Phase 2 candidate.

## Run (Cloud Shell has Terraform and GCP auth built in)

    cd terraform
    terraform init
    terraform plan     # expect: No changes
    terraform apply    # only when the plan shows the change you intend

## State
Remote state is stored in `gs://market-bubble-alert-tfstate` (versioned).
That bucket was created once by hand and is intentionally not managed here.
