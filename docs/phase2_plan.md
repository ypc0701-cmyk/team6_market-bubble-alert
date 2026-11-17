# Phase 2 plan and lane descriptions

BA882 Fall 2026 · Nov 11, 2026 · re-baselined Nov 16 · Phase 2 freeze on Nov 25, 2026 · draft for team review

This document turns the agreed Phase 2 proposal ([phase2_proposal.md](phase2_proposal.md), PR #68) into a plan, covering what the Phase 1 plan and lane descriptions covered together: the lanes and owners, the dependency chain, weekly milestones, each lane's tasks, interfaces, dates and definition of done, and the full schedule.

**Re-baseline, Nov 16.** The rules and contract v0.3 were circulated on Nov 16 (PR #99), four days later than first planned, so the freeze of the rules moves to Nov 18 and the Phase 2 freeze moves from Nov 23 to Nov 25. Every date below is the new one. Lanes 1 and 2 do not need to wait for the freeze: universe mode and the feature and label models can be built now against the dummy rows in `docs/dummy_rows/phase2/`.

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

- **Phase 2 rules and schema contract v0.3 (Lane 3, frozen Wed Nov 18)** is the chokepoint, as the schema contract was in Phase 1. It fixes the universe rules, the label, the time split, the feature list and the columns of every new table. The universe list is selected only after the rules are merged: the ETF holdings snapshot is taken on Nov 19.
- **Data flow:** universe list fixed (Lane 3, Nov 19) → universe seeded (Lane 2, Nov 19) → backfill loaded (Lane 1, Nov 20) → features and labels (Lane 2, Nov 21) → models trained and scored (Lane 2, Nov 22) → API and dashboard on real scores (Lanes 5 and 4, Nov 23 to 24).
- **Evaluation path:** baselines (Lane 3, Nov 22) → models versus baselines on the test period (Lane 3, Nov 23) → our 11 scored and the larger-basket dial (Lane 3, Nov 24).
- **Platform first:** MLflow and the API skeleton (Lane 5, Nov 18) come before the first training run.
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

- Nov 17 (Tue): comments on the Phase 2 rules and contract (PR #99)
- Nov 19 (Thu): extractor reads `universe_members`; dry run on the frozen universe
- Nov 20 (Fri): backfill to 2020 loaded in BigQuery
- Nov 22 (Sun): weekly Airflow tasks scheduled (features, retrain, score)
- Nov 23 (Mon): first weekly run green (triggered by hand; on its Friday schedule from Nov 27)

### Definition of done (Nov 25)

- Daily DAG still green, now covering the universe.
- At least one weekly run (features, retrain, score) green end to end, with its MLflow run linked from the logs.
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

- Nov 17 (Tue): comments on the contract; training engine decision with Lanes 3 and 5
- Nov 19 (Thu): `universe_members` seeded, with tests; `prices_raw` ticker test accepts the universe
- Nov 21 (Sat): weekly features and labels building on the backfill
- Nov 22 (Sun): training and scoring models running; `model_scores` populated

### Definition of done (Nov 25)

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
- **Schema contract v0.3:** Columns for `universe_members`, `weekly_features`, `weekly_labels` and `model_scores`, plus dummy rows, circulated Monday Nov 16 and frozen Wednesday Nov 18.
- **Evaluation:** Both baselines (drawdown only, volatility only), then the models. Report AUC, precision of the top 10% of scores and calibration on the test period, with block-bootstrap error bars because weekly rows share overlapping 60-day labels.
- **Our 11:** Score them out of sample and answer the proposal's question: are our picks riskier than the typical AI stock?
- **Larger-basket dial:** Run the Phase 1 dial logic on the universe as a robustness check, next to the official dial, reusing the Phase 1 marts.
- **Known limits:** Measure how much the hindsight universe (today's ETF holdings) and survivorship move the results, and write it next to every number.
- **Decision log and methodology:** Phase 2 entries for every rule above.

### Interfaces

- **Produces:** The rules and contract every lane builds against; the evaluation everyone presents; the larger-basket dial.
- **Consumes:** Weekly features and labels from Lane 2; MLflow runs from Lane 5.

### Key dates for this lane

- Nov 16 (Mon): draft Phase 2 rules and contract v0.3 circulated (PR #99)
- Nov 18 (Wed): RULES AND CONTRACT FROZEN, the chokepoint (PR #99 merged)
- Nov 19 (Thu): ETF holdings snapshot taken; universe list fixed and handed to Lane 2
- Nov 22 (Sun): label base rate and both baselines computed
- Nov 23 (Mon): evaluation report: models versus baselines on the test period
- Nov 24 (Tue): larger-basket dial built; our 11 scored out of sample
- Nov 24 (Tue): decision log Phase 2 entries completed (rules R1 to R8 were logged Nov 16)

### Definition of done (Nov 25)

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

- Nov 17 (Tue): comments on the contract
- Nov 19 (Thu): panels on dummy rows
- Nov 24 (Tue): panels on real scores and the larger-basket dial
- Nov 25 (Wed): polish freeze; Cloud Run redeploy verified

### Definition of done (Nov 25)

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
- **Integration:** Run the Nov 24 integration check with a written punch list.
- **AI log:** Kept current for Phase 2.

### Interfaces

- **Produces:** The MLflow server and API others build on; the board; the paper trail.
- **Consumes:** Scores from Lane 2; monitoring definitions from Lane 3; status from every lane.

### Key dates for this lane

- Nov 12 (Thu): Phase 2 milestone and issues created; MLflow hosting decision
- Nov 17 (Tue): training engine decision with Lanes 2 and 3
- Nov 18 (Wed): MLflow server live; API skeleton serving contract dummy rows
- Nov 23 (Mon): API serving real scores
- Nov 24 (Tue): integration check with punch list; monitoring tables live

### Definition of done (Nov 25)

- MLflow shows every training run with parameters, metrics and model version.
- The API answers `/risk?ticker=NVDA` and `/basket` from live scores.
- Board reflects reality; AI log current.

## Schedule and dependencies

Everything in one place, sorted by date. As in Phase 1: before starting an item, check that what it depends on has landed, and escalate in the team channel the same day if it has not.

| Date | Lane | Deliverable | Depends on |
| --- | --- | --- | --- |
| Nov 11 (Wed) | All | Phase 2 proposal agreed (PR #68 merged) | None |
| Nov 12 (Thu) | 5 | Phase 2 milestone and issues created; MLflow hosting decision | This document |
| Nov 16 (Mon) | 3 | Draft Phase 2 rules and contract v0.3 circulated (PR #99) | Proposal |
| Nov 17 (Tue) | 1, 2, 4, 5 | Comments on the rules and contract | Draft (Lane 3, Nov 16) |
| Nov 17 (Tue) | 2, 3, 5 | Training engine decided: BigQuery ML or Python | None |
| Nov 17 (Tue) | All | Session 10 (deployment, monitoring); Quiz 3 | None |
| Nov 18 (Wed) | 3 | RULES AND CONTRACT v0.3 FROZEN (PR #99 merged) | Comments (Nov 17) |
| Nov 18 (Wed) | 5 | MLflow live; API skeleton on dummy rows | GCP access |
| Nov 19 (Thu) | 3 | ETF snapshot taken; universe list fixed | Rules merged |
| Nov 19 (Thu) | 2 | `universe_members` seeded, with tests | Universe list (Lane 3) |
| Nov 19 (Thu) | 1 | Extractor reads `universe_members` | Seed (Lane 2) |
| Nov 19 (Thu) | 4 | Panels on contract dummy rows | Contract (Lane 3) |
| Nov 20 (Fri) | 1 | Universe backfill to 2020 loaded | Extractor universe mode; Phase 1 calendar floor |
| Nov 21 (Sat) | 2 | Weekly features and labels building | Backfill (Lane 1) |
| Nov 22 (Sun) | 3 | Label base rate and baselines computed | Features and labels (Lane 2) |
| Nov 22 (Sun) | 2 | Models trained and logged; `model_scores` populated | Features, labels; MLflow (Lane 5) |
| Nov 22 (Sun) | 1 | Weekly Airflow tasks scheduled | Training and scoring entry points |
| Nov 23 (Mon) | 3 | Evaluation report: models versus baselines | Trained models |
| Nov 23 (Mon) | 5 | API serving real scores | `model_scores` |
| Nov 23 (Mon) | 1 | First weekly run green (triggered by hand) | Weekly tasks |
| Nov 24 (Tue) | 3 | Larger-basket dial; our 11 scored out of sample | Backfill; scores |
| Nov 24 (Tue) | 4 | Panels on real scores and the larger-basket dial | Scores; dial (Lane 3) |
| Nov 24 (Tue) | 5, all | Integration check with punch list; monitoring live | Everything above |
| Nov 24 (Tue) | All | Phase 3 (GenAI) starts in class; overlaps the last two days of Phase 2 | None |
| Nov 25 (Wed) | All | Phase 2 freeze | Punch list closed |

The Phase 2 due date and presentation format are still to be confirmed with the professor; the graded presentations in the original proposal are Oct 27 and Dec 8.

## Milestones

**Week 1 · Nov 10 to 18 · rules first, then platform**

- [x] Phase 2 proposal agreed (all, Nov 11)
- [x] Phase 2 milestone and issues on the board (Nov 12)
- [x] Rules and contract v0.3 circulated (lane 3, Nov 16, PR #99)
- [ ] Comments on the rules and contract (lanes 1, 2, 4, 5, Nov 17)
- [ ] Training engine decided: BigQuery ML or Python (lanes 2, 3, 5, Nov 17)
- [ ] Rules and contract v0.3 frozen (lane 3, Nov 18)
- [ ] MLflow live; API skeleton on dummy rows (lane 5, Nov 18)

**Week 2 · Nov 19 to 25 · data, train, judge, serve, freeze**

- [ ] ETF snapshot; universe list fixed (lane 3, Nov 19)
- [ ] `universe_members` seeded with tests (lane 2, Nov 19)
- [ ] Dashboard panels on dummy rows (lane 4, Nov 19)
- [ ] Universe backfill to 2020 in BigQuery (lane 1, Nov 20)
- [ ] Weekly features and labels building (lane 2, Nov 21)
- [ ] Baselines and label base rate (lane 3, Nov 22)
- [ ] Models trained, logged in MLflow, scores populated (lane 2, Nov 22)
- [ ] Weekly Airflow tasks scheduled; first weekly run green (lane 1, Nov 22 to 23)
- [ ] Evaluation report: models versus baselines (lane 3, Nov 23)
- [ ] API serving real scores (lane 5, Nov 23)
- [ ] Larger-basket dial; our 11 scored out of sample (lane 3, Nov 24)
- [ ] Panels on real data (lane 4, Nov 24)
- [ ] Integration check with punch list; monitoring live (lane 5 and all, Nov 24)
- [ ] Phase 2 freeze (all, Nov 25)

## Housekeeping

- [ ] AI log: keep adding entries during Phase 2 (all, lane 5 owns the file)
- [ ] Decision log: Phase 2 rules and their reasons, written before training (lane 3)
- [ ] Phase 1 leftovers: close #36 (presentation done) and confirm #24 (five green runs) (lanes 3 and 1)

## How the lanes fit together

Lane 3 writes the rules, Lane 1 lands the universe, Lane 2 turns it into features, labels and scores, Lane 5 tracks and serves the model, and Lane 4 shows it. Contract v0.3 (frozen Nov 18) is the only hard dependency in the first week; after that, integration happens through the shared warehouse, as in Phase 1.

## Decisions still open

| Decision | Owner | Due |
| --- | --- | --- |
| Which AI-themed ETFs define the universe | Lane 3 | Rule proposed Nov 16 (decision log R1); frozen Nov 18 |
| Label thresholds (20% / 60 days) confirmed | Lane 3 | Nov 18 (frozen), Nov 22 (base-rate check) |
| BigQuery ML or Python for training | Lanes 2, 3, 5 | Nov 17 (BigQuery ML proposed, decision log R8) |
| MLflow hosting within course credits | Lane 5 | Decided Nov 13 (PR #97) |
| Phase 2 due date and presentation format | Lane 5 asks the professor | Nov 17 class |
