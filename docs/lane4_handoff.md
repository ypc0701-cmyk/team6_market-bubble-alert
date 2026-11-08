# Lane 4 Phase 1 handoff

Status checked October 26, 2026. Owner: Yuanhao Li.

## Code and review status

- PR #60 is merged. It adds evidence, basket comparison, credit/concentration plots and episodes using existing marts.
- PR #58 is merged. It documents the service URL and runtime IAM roles.
- PR #61 is merged. Methodology section 4 supplies the approved AI-specific qualifier and section 5 records roster hindsight.
- This follow-up applies the qualifier only when every active, listed symbol has a price. Missing/failed coverage retains the audit warning. It also labels confirmation as held once.
- Local validation: 29 mocked UI checks passed. No BigQuery production query or Cloud Run deployment was executed by this check.

## Evidence already available

Issue #44 records a successful latest-main Astronomer run of extract_and_load followed by dbt_build. The original Cloud Run release and team browser access were verified on October 20.

A user-provided Cloud Shell dashboard PDF reads production marts with trade_date 2026-10-23 and computed_at 2026-10-24 19:23 UTC. It shows Level 2 DIVERGENCE, credit normal, armed since 2025-10-22, 10/11 eligible speculative members broken, breadth 90.9%, speculative median drawdown -61.2%, S&P distance -2.5%, and credit distance -2.5%. This is a dated illustration, not a fresh Cloud Run acceptance run. Eligible counts alone do not prove full-roster price coverage.

## Complete the release

1. Review and merge this follow-up using the team's one-approval workflow.
2. Deploy dashboard/ from the reviewed main branch using dashboard/README.md. Keep IAP and the existing read-only runtime identity.
3. Record the deployed revision and commit, the tester and the check time. Run dashboard/verify_production.sql and retain its output.
4. In Cloud Run, confirm dataset marts, the same latest trade_date, and the matching verdict, explanation, credit, armed-since date and broken/eligible count. Compare the evidence values and episode dates with SQL.
5. Check full-roster price coverage. Show the AI-specific qualifier only with no missing prices. Verify History and Members do not change the latest verdict, refresh works, and episode end is not described as disarming.
6. After a successful upstream build, confirm a later page refresh reflects the updated marts. Keep an authorized teammate's access check, screenshots and a short fallback recording with the demo materials.

## Close the issues

For #51, attach the approved Methodology section 4 wording, the follow-up PR, and the deployed clean/missing-coverage checks. Mark its final acceptance item only after the deployed behavior is confirmed.

For #52, the URL/IAM documentation is now present. Complete its remaining documentation item after this handoff and AI log are merged. Attach the deployed revision, SQL comparison, team access check and walkthrough before marking the final item and closing.

## Demo sequence

Astronomer: show a green run and both tasks. BigQuery: identify the matching raw and mart trading dates. daily_signals: read the latest verdict in one SELECT. Dashboard: show that same date and verdict, the evidence, basket comparison, member switching and one episode. Explain filter scope and the data-quality condition behind the AI-specific qualifier.

## Presentation snapshot

The Cloud Reporting slide uses the dated October 23 snapshot. Keep its date explicit. The neighboring Lane 3 slide refers to the earlier reading with the S&P within 1% of its high; give that slide its own as-of date or refresh both from one verified snapshot before presenting. Do not change -2.5% to 1% merely to make the slides agree.
