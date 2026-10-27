# Terraform

Manages the core GCP resources for `market-bubble-alert`:
- GCS bucket `market-bubble-alert-landing`
- BigQuery datasets `raw`, `staging`, `marts`
- Service account `airflow-pipeline`

These were created by hand on Oct 11 so Lane 1 was not blocked, then imported with
the `import` blocks in `imports.tf` on Oct 20 (no changes to the live resources).
IAM role bindings, the `dashboard-runtime` service account and the Cloud Run service
are still managed by hand (see the IAM table in the root README) and are Phase 2 candidates.

## When to run Terraform

Terraform is not part of the daily pipeline and does not run on its own. These are
team rules, not automation: nothing enforces them yet, so reviewers check them.

1. **Infrastructure changes go through Terraform.** To add or change a bucket,
   dataset or service account listed above, edit the `.tf` files and open a PR.
   Do not change these resources in the GCP console.
2. **A PR that touches `terraform/` includes a plan.** Run `terraform plan` on the
   PR branch and paste the summary line (for example `Plan: 1 to add, 0 to change,
   0 to destroy`) into the PR. The reviewer checks that it shows only the intended
   change. After merge, Lane 5 runs `terraform apply` from `main`.
3. **Drift check before each phase.** Lane 5 runs `terraform plan` on `main` before
   each phase starts (next: before Phase 2, Nov 10). Anything other than
   `No changes` means someone changed a resource outside Terraform; find out who and
   why, then either update the `.tf` files or apply to restore the settings.
4. **Planned automation (Phase 2):** a GitHub Action that runs `terraform plan` on
   every PR touching `terraform/` and on a schedule, so rules 2 and 3 no longer
   depend on someone remembering.

Never run `terraform apply` when the plan shows a `change` or `destroy` you did not
expect. Stop and ask in the team channel.

## Run

Cloud Shell has GCP auth but not Terraform. Install it once into your home folder
(it persists across Cloud Shell sessions):

    TF_VERSION=1.9.8
    mkdir -p ~/bin
    curl -sLo /tmp/terraform.zip "https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_amd64.zip"
    unzip -o -q /tmp/terraform.zip terraform -d ~/bin
    grep -q 'HOME/bin' ~/.bashrc || echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/bin:$PATH"

Then, from the repo:

    cd terraform
    terraform init
    terraform plan     # on main, expect: No changes
    terraform apply    # only when the plan shows the change you intend

If a plan fails with `connection refused`, it is a transient Cloud Shell network
error; rerun it, or add `-parallelism=1`.

## State
Remote state is stored in `gs://market-bubble-alert-tfstate` (versioned).
That bucket was created once by hand and is intentionally not managed here.
