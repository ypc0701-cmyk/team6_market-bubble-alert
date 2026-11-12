# Phase 2 plan and lane descriptions

BA882 Fall 2026 · Nov 11, 2026 · two weeks to the Phase 2 freeze on Nov 23, 2026 · draft for team review

This document turns the agreed Phase 2 proposal ([phase2_proposal.md](phase2_proposal.md), PR #68) into a plan, covering what the Phase 1 plan and lane descriptions covered together: the lanes and owners, the dependency chain, weekly milestones, each lane's tasks, interfaces, dates and definition of done, and the full schedule.

## The five lanes

Owners stay the same as in Phase 1.

| Lane | Phase 2 scope | Owner |
| --- | --- | --- |
| 1 · Ingestion + orchestration | Universe prices (backfill to 2020) through the existing extractor; weekly Airflow tasks for features, retraining and scoring | Kean |
| 2 · Warehouse + dbt | `universe_members`; weekly feature and label tables; training and scoring models; `model_scores`; tests | Ahrar |
| 3 · Signal logic | Phase 2 rules and schema contract v0.3; evaluation against baselines; our 11 scored out of sample; larger-basket dial | Javier |
| 4 · Dashboard | Risk panel, robustness panel and model card in the Streamlit app | Myhill |
| 5 · Platform + PM | MLflow server; Cloud Run API; IAM and cost; Phase 2 board; monitoring; AI log | Chloe |

## Dependency chain

- **Phase 2 rules and schema contract v0.3 (Lane 3, frozen Sat Nov 14)** is the chokepoint, as the schema contract was in Phase 1. It fixes the universe rules, the label, the time split, the feature list and the columns of every new table. The universe list is selected only after the rules are logged.
- **Data flow:** universe seeded (Lane 2, Nov 15) → backfill loaded (Lane 1, Nov 16) → features and labels (Lane 2, Nov 17) → models trained and scored (Lane 2, Nov 19) → API and dashboard on real scores (Lanes 5 and 4, Nov 20 to 21).
- **Evaluation path:** baselines (Lane 3, Nov 18) → models versus baselines on the test period (Lane 3, Nov 20) → our 11 scored and the larger-basket dial (Lane 3, Nov 21).
- **Platform first:** MLflow and the API skeleton (Lane 5, Nov 16) come before the first training run.
- Blocked by a missing dependency? Escalate in the team channel that day.

## Lane 1 · Ingestion and orchestration

Get prices for the larger AI universe landing every trading day, and run the weekly ML steps without a human touching them.

### What this lane owns

The extractor's universe mode, the backfill, and the Phase 2 tasks in the Airflow DAG.

### Tasks

- **Universe mode:** Extend the extractor to read its ticker list from `universe_members` instead of the hard-coded Phase 1 list. Phase 1 tickers keep loading exactly as today.
- **Backfill:** One-off load of daily adjusted close and volume for every universe ticker back to Jan 2020 (or its listing date), idempotent like the Phase 1 backfill.
- **Rate limits:** Check yfinance holds up for about 150 tickers per day; route failures through the existing Tiingo fallback and log the source per ticker.
- **Weekly tasks:** Add Airflow tasks after the daily `dbt build`, running Fridays after the close: build weekly features and labels, retrain, score, log to MLflow. A failed weekly task must alert in Slack like the daily ones.
- **Universe refresh:** A documented, manual step to re-pull ETF holdings when Lane 3 asks; never automatic, so the universe only changes by logged decision.

### Interfaces

- **Produces:** Universe prices in `raw.prices_raw` (same table and contract as Phase 1); green weekly runs visible in Astronomer.
- **Consumes:** `universe_members` from Lane 2; the training and scoring entry points from Lanes 2 and 5.

### Key dates for this lane

- Nov 13 (Fri): comments on the Phase 2 rules and contract
- Nov 15 (Sun): extractor reads `universe_members`; dry run on the frozen universe
- Nov 16 (Mon): backfill to 2020 loaded in BigQuery
- Nov 19 (Thu): weekly Airflow tasks scheduled (features, retrain, score)
- Nov 20 (Fri): first scheduled weekly run green

### Definition of done (Nov 23)

- Daily DAG still green, now covering the universe.
- At least one scheduled weekly run (features, retrain, score) green end to end, with its MLflow run linked from the logs.
- README section: how to backfill a new universe ticker.

## Lane 2 · Warehouse and dbt

Turn universe prices into tested weekly feature and label tables, and own the training and scoring models in the warehouse.

### What this lane owns

`universe_members`, the weekly feature and label models, the scores table, and their tests.

### Tasks

- **Universe seed:** `universe_members` as a slowly changing dimension modeled on `basket_members` (ticker, source ETF, added_date, removed_date, reason), seeded from the list Lane 3 freezes, with tests (no overlap with our 11, no duplicate spans).
- **Weekly features:** One row per ticker per Friday close, every column in contract v0.3, computed only from data available on that date. Tests for nulls, ranges and one row per (ticker, week).
- **Weekly labels:** The label exactly as Lane 3 writes it, NULL for the most recent 60 trading days. A dbt test proves no label uses a price before its own date.
- **Training and scoring:** If the team picks BigQuery ML: `CREATE MODEL` and `ML.PREDICT` as dbt models. If Python: the training-set and scoring-input views the Python job reads. Either way, the scores land in `marts.model_scores`.
- **Docs:** Lineage graph extended to the Phase 2 tables for the demo.

### Interfaces

- **Produces:** `universe_members`, `weekly_features`, `weekly_labels`, `model_scores`.
- **Consumes:** Universe prices from Lane 1; contract v0.3 and the rules from Lane 3.

### Key dates for this lane

- Nov 13 (Fri): comments on the contract; training engine decision with Lanes 3 and 5
- Nov 15 (Sun): `universe_members` seeded, with tests
- Nov 17 (Tue): weekly features and labels building on the backfill
- Nov 19 (Thu): training and scoring models running; `model_scores` populated

### Definition of done (Nov 23)

- `dbt build` passes with the Phase 2 models and tests on the daily schedule.
- A seeded future-dated row demonstrably fails the leakage test (the observability story for Phase 2).
- Lineage graph shows prices to features to scores.

## Lane 3 · Signal logic

Write the rules before anyone trains, then judge the model honestly against them.

### What this lane owns

The Phase 2 rules, schema contract v0.3, the evaluation, and the larger-basket dial.

### Tasks

- **Phase 2 rules (decision log, before any ticker is selected):** Universe rules (which AI-themed ETFs, price above $2, average daily trading above $5M, 60+ trading days), our 11 excluded by rule from training rows and from basket-level features, and the snapshot date logged.
- **Label and split:** Confirm or adjust the 20% / 60-trading-day label with a base-rate check on the backfill. Fix the train, validation and test periods with 60-trading-day gaps.
- **Feature list:** Final list for contract v0.3. Every feature must exist for the whole 2020 to 2026 training period, so the official dial level (only available from late 2024, and built from our 11) is replaced by breadth of the larger basket.
- **Schema contract v0.3:** Columns for `universe_members`, `weekly_features`, `weekly_labels` and `model_scores`, plus dummy rows, circulated Thursday and frozen Saturday.
- **Evaluation:** Both baselines (drawdown only, volatility only), then the models. Report AUC, precision of the top 10% of scores and calibration on the test period, with block-bootstrap error bars because weekly rows share overlapping 60-day labels.
- **Our 11:** Score them out of sample and answer the proposal's question: are our picks riskier than the typical AI stock?
- **Larger-basket dial:** Run the Phase 1 dial logic on the universe as a robustness check, next to the official dial, reusing the Phase 1 marts.
- **Known limits:** Measure how much the hindsight universe (today's ETF holdings) and survivorship move the results, and write it next to every number.
- **Decision log and methodology:** Phase 2 entries for every rule above.

### Interfaces

- **Produces:** The rules and contract every lane builds against; the evaluation everyone presents; the larger-basket dial.
- **Consumes:** Weekly features and labels from Lane 2; MLflow runs from Lane 5.

### Key dates for this lane

- Nov 12 (Thu): draft Phase 2 rules and contract v0.3 circulated
- Nov 14 (Sat): RULES AND CONTRACT FROZEN, the chokepoint; universe list fixed after the rules are logged
- Nov 18 (Wed): label base rate and both baselines computed
- Nov 20 (Fri): evaluation report: models versus baselines on the test period
- Nov 21 (Sat): larger-basket dial built; our 11 scored out of sample
- Nov 22 (Sun): decision log Phase 2 entries committed

### Definition of done (Nov 23)

- Rules logged before the universe was selected, with dates to prove it.
- Evaluation report with error bars, stating plainly whether the model beats the baselines.
- Larger-basket dial queryable with one SELECT, next to the official dial.

## Lane 4 · Dashboard

Show the risk scores and the robustness check in five seconds, with the dial still the first thing people see.

### What this lane owns

The Phase 2 panels in the Streamlit app and its redeploy.

### Tasks

- **Risk panel:** Our 11 with their drop probability, rank in the universe and change since last week, next to the universe distribution.
- **Robustness panel:** Larger-basket dial next to the official dial, with one sentence on how to read agreement or disagreement.
- **Model card:** Model version, last-trained date, test-period AUC and the baseline it beat (or did not), read from the scores and evaluation tables.
- **API or warehouse:** Read scores through the Cloud Run API where practical, so the demo shows the model being served; fall back to BigQuery if the API is down.
- **Dummy-data start:** Build against the contract v0.3 dummy rows first, then swap to real tables without layout changes.

### Interfaces

- **Produces:** The Phase 2 part of the demo.
- **Consumes:** `model_scores` and the evaluation from Lanes 2 and 3; the API from Lane 5; contract v0.3 dummy rows.

### Key dates for this lane

- Nov 13 (Fri): comments on the contract
- Nov 15 (Sun): panels on dummy rows
- Nov 21 (Sat): panels on real scores and the larger-basket dial
- Nov 22 (Sun): polish freeze; Cloud Run redeploy verified

### Definition of done (Nov 23)

- Panels load from live tables (or the API) with zero manual steps.
- A stranger can say whether our 11 are riskier than the typical AI stock after ten seconds.
- The model card states plainly whether ML beat the simple rules.

## Lane 5 · Platform and PM

Stand up the ML platform pieces and keep the project board telling the truth.

### What this lane owns

The MLflow server, the Cloud Run API, IAM and cost, the Phase 2 milestone and issues, and the AI log.

### Tasks

- **MLflow:** Tracking server on Cloud Run with artifacts in GCS (Terraform where practical), reachable by the training job and by every member.
- **Cloud Run API:** `GET /risk?ticker=` and `GET /basket` reading the latest weekly scores from BigQuery, as specified in the proposal; read-only service account like the dashboard's.
- **IAM and cost:** BigQuery ML or Vertex permissions for the training job; budget check on the larger universe and the new services.
- **Board:** Phase 2 milestone and issues created from this document, assigned by lane, with acceptance criteria.
- **Monitoring:** With Lane 3, the rolling accuracy and calibration table and the feature drift check; API health (errors, latency).
- **Integration:** Run the Nov 22 integration check with a written punch list.
- **AI log:** Kept current for Phase 2.

### Interfaces

- **Produces:** The MLflow server and API others build on; the board; the paper trail.
- **Consumes:** Scores from Lane 2; monitoring definitions from Lane 3; status from every lane.

### Key dates for this lane

- Nov 12 (Thu): Phase 2 milestone and issues created; MLflow hosting decision
- Nov 13 (Fri): training engine decision with Lanes 2 and 3
- Nov 16 (Mon): MLflow server live; API skeleton serving contract dummy rows
- Nov 20 (Fri): API serving real scores
- Nov 22 (Sun): integration check with punch list; monitoring tables live

### Definition of done (Nov 23)

- MLflow shows every training run with parameters, metrics and model version.
- The API answers `/risk?ticker=NVDA` and `/basket` from live scores.
- Board reflects reality; AI log current.

## Schedule and dependencies

Everything in one place, sorted by date. As in Phase 1: before starting an item, check that what it depends on has landed, and escalate in the team channel the same day if it has not.

| Date | Lane | Deliverable | Depends on |
| --- | --- | --- | --- |
| Nov 11 (Wed) | All | Phase 2 proposal agreed (PR #68 merged) | None |
| Nov 12 (Thu) | 3 | Draft Phase 2 rules and contract v0.3 circulated | Proposal |
| Nov 12 (Thu) | 5 | Phase 2 milestone and issues created; MLflow hosting decision | This document |
| Nov 13 (Fri) | 1, 2, 4, 5 | Comments on the rules and contract | Draft (Lane 3, Nov 12) |
| Nov 13 (Fri) | 2, 3, 5 | Training engine decided: BigQuery ML or Python | None |
| Nov 14 (Sat) | 3 | RULES AND CONTRACT v0.3 FROZEN; universe list fixed | Comments (Nov 13) |
| Nov 15 (Sun) | 2 | `universe_members` seeded, with tests | Frozen list (Lane 3) |
| Nov 15 (Sun) | 1 | Extractor reads `universe_members` | Seed (Lane 2) |
| Nov 15 (Sun) | 4 | Panels on contract dummy rows | Contract (Lane 3) |
| Nov 16 (Mon) | 1 | Universe backfill to 2020 loaded | Extractor universe mode |
| Nov 16 (Mon) | 5 | MLflow live; API skeleton on dummy rows | GCP access |
| Nov 17 (Tue) | 2 | Weekly features and labels building | Backfill (Lane 1) |
| Nov 17 (Tue) | All | Session 10 (deployment, monitoring); Quiz 3 | None |
| Nov 18 (Wed) | 3 | Label base rate and baselines computed | Features and labels (Lane 2) |
| Nov 19 (Thu) | 2 | Models trained and logged; `model_scores` populated | Features, labels; MLflow (Lane 5) |
| Nov 19 (Thu) | 1 | Weekly Airflow tasks scheduled | Training and scoring entry points |
| Nov 20 (Fri) | 3 | Evaluation report: models versus baselines | Trained models |
| Nov 20 (Fri) | 5 | API serving real scores | `model_scores` |
| Nov 20 (Fri) | 1 | First scheduled weekly run green | Weekly tasks |
| Nov 21 (Sat) | 3 | Larger-basket dial; our 11 scored out of sample | Backfill; scores |
| Nov 21 (Sat) | 4 | Panels on real scores and the larger-basket dial | Scores; dial (Lane 3) |
| Nov 22 (Sun) | 5, all | Integration check with punch list; monitoring live | Everything above |
| Nov 23 (Mon) | All | Phase 2 freeze | Punch list closed |
| Nov 24 (Tue) | All | Phase 3 (GenAI) starts | Freeze |

The Phase 2 due date and presentation format are still to be confirmed with the professor; the graded presentations in the original proposal are Oct 27 and Dec 8.

## Milestones

**Week 1 · Nov 10 to 16 · rules first, then data and platform**

- [ ] Phase 2 proposal agreed (all, Nov 11)
- [ ] Phase 2 milestone and issues on the board (lane 5, Nov 12)
- [ ] Rules and contract v0.3 frozen; universe list fixed (lane 3 drafts Nov 12, frozen Nov 14)
- [ ] Training engine decided: BigQuery ML or Python (lanes 2, 3, 5, Nov 13)
- [ ] `universe_members` seeded with tests (lane 2, Nov 15)
- [ ] Universe backfill to 2020 in BigQuery (lane 1, Nov 16)
- [ ] MLflow live; API skeleton on dummy rows (lane 5, Nov 16)
- [ ] Dashboard panels on dummy rows (lane 4, Nov 15)

**Week 2 · Nov 17 to 23 · train, judge, serve, freeze**

- [ ] Weekly features and labels building (lane 2, Nov 17)
- [ ] Baselines and label base rate (lane 3, Nov 18)
- [ ] Models trained, logged in MLflow, scores populated (lane 2, Nov 19)
- [ ] Weekly Airflow tasks scheduled; first weekly run green (lane 1, Nov 19 to 20)
- [ ] Evaluation report: models versus baselines (lane 3, Nov 20)
- [ ] API serving real scores (lane 5, Nov 20)
- [ ] Larger-basket dial; our 11 scored out of sample (lane 3, Nov 21)
- [ ] Panels on real data (lane 4, Nov 21)
- [ ] Integration check with punch list; monitoring live (lane 5 and all, Nov 22)
- [ ] Phase 2 freeze (all, Nov 23)

## Housekeeping

- [ ] AI log: keep adding entries during Phase 2 (all, lane 5 owns the file)
- [ ] Decision log: Phase 2 rules and their reasons, written before training (lane 3)
- [ ] Phase 1 leftovers: close #36 (presentation done) and confirm #24 (five green runs) (lanes 3 and 1)

## How the lanes fit together

Lane 3 writes the rules, Lane 1 lands the universe, Lane 2 turns it into features, labels and scores, Lane 5 tracks and serves the model, and Lane 4 shows it. Contract v0.3 (frozen Nov 14) is the only hard dependency in the first week; after that, integration happens through the shared warehouse, as in Phase 1.

## Decisions still open

| Decision | Owner | Due |
| --- | --- | --- |
| Which AI-themed ETFs define the universe | Lane 3 | Nov 14 |
| Label thresholds (20% / 60 days) confirmed | Lane 3 | Nov 14 (draft), Nov 18 (base-rate check) |
| BigQuery ML or Python for training | Lanes 2, 3, 5 | Nov 13 |
| MLflow hosting within course credits | Lane 5 | Nov 12 |
| Phase 2 due date and presentation format | Lane 5 asks the professor | Next class |
