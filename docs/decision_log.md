# Decision Log

## Dashboard tool and deployment

- Recorded: 2026-10-20
- Owner: Yuanhao (Myhill), Lane 4
- Decision: Streamlit for the dashboard, with Cloud Run as the deployment target.
- Alternative considered: Looker, which offers a simpler managed BigQuery connection.
- Reason: Streamlit gives us control over the verdict cards, event annotations, and member views in Python. The prototype already runs against real development marts.
- Tradeoff: the team maintains an application image, dependency versions, runtime identity, and access configuration. Cloud Run deployment and team access still need live verification.
- Review: Javier approved PR #53; merged on 2026-10-20.
- Verification: production data reads were verified in Cloud Shell on 2026-10-20. Cloud Run deployment and team access remain pending.

### Data and display boundary

All signal calculations stay in dbt. The dashboard reads daily_signals, daily_drawdowns, and basket_members. Its member query uses the latest signal's trading date. Percentage formatting, sorting, date filtering, and freshness notices are display operations.

Development uses marts_dev; production explicitly selects marts. Failed production reads remain visible. The display warns after 72 hours since calculation or at least two weekday sessions of signal-date lag, allowing the evening update until 7pm ET. The weekday check excludes weekends but does not model exchange holidays; Lane 2 owns source freshness checks.

The generic basket-audit warning is implemented. The final AI-specific qualifier will be agreed with Lane 3 before acceptance of #51.

## Least-privilege identities for the pipeline and the dashboard

- Recorded: 2026-10-20
- Owner: Chloe, Lane 5
- Decision: Each workload runs as its own service account with only the roles it needs. `airflow-pipeline` writes to GCS and BigQuery for the DAG. `dashboard-runtime` can run queries and read the `marts` dataset only, with no access to `raw` or `staging` and no write access.
- Alternative considered: one shared service account, or running the dashboard as the DAG's account.
- Reason: a bug or a leaked credential in the dashboard cannot change or delete pipeline data. Team members get roles by lane for the same reason.
- Tradeoff: more identities to document and maintain; role changes go through Lane 5.
- Lesson: on Oct 12, Python clients running locally with user credentials failed with a 403 until members got Service Usage Consumer; the README IAM table records it.

## Infrastructure as code

- Recorded: 2026-10-20
- Owner: Chloe, Lane 5
- Decision: The landing bucket, the `raw`, `staging` and `marts` datasets and the DAG service account are managed by Terraform, with remote state in `gs://market-bubble-alert-tfstate` (versioned).
- How we got there: the resources were created by hand on Oct 11 so Lane 1 could load data at once, then imported on Oct 20 with Terraform import blocks; the import changed nothing on the live resources (PR #56).
- Tradeoff: IAM bindings, the dashboard service account and the Cloud Run service are still managed by hand for Phase 1; moving them into Terraform is a Phase 2 candidate.
