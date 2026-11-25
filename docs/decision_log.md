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

## Signal logic (Lane 3)

Entries are ordered by the date the decision was taken. "M §n" points to the section of `docs/methodology.md` that carries the reasoning; "C §n" to `docs/schema_contract.md`. Thresholds were fixed before the first real run (2026-10-15) and have not been tuned against live data since.

## Build the signal from scratch instead of productionizing the prototype

- Recorded: 2026-10-07
- Owner: Javier, Lane 3
- Decision: The warehouse implements the Methodology document directly in dbt. The pre-project Python monitor is retired as a reference and shares no code with the marts.
- Alternative considered: wrapping the prototype's functions in the pipeline and writing the marts from its outputs.
- Reason: the prototype carried the color-stage state machine and a basket-average breadth that the Methodology had already rejected, and its logic lived in loops that cannot be expressed as reproducible SQL over a backfill. Writing the Methodology first and deriving tables from it gives every column a paragraph to trace back to (M §6) and lets a second, independent implementation serve as the test oracle instead of the thing under test.
- Tradeoff: one more week before any mart existed; the schema contract (frozen 2026-10-10) absorbed that delay so other lanes could start against dummy rows.
- Review: contract PR #25 opened 2026-10-12 and merged 2026-10-14.

## Breadth and median drawdown instead of a basket average

- Recorded: 2026-10-07 (M §2)
- Owner: Javier, Lane 3
- Decision: The speculative basket is read as breadth (share of mature members at least 25% below their reference high) and the median member drawdown. No capitalization- or equal-weighted basket index is computed.
- Alternative considered: an equal-weighted average return of the basket, which the prototype used.
- Reason: in the prototype one member (Nebius, up 209% in six months) masked nine members sitting 26 to 65% below their highs; the average read calm while nine of ten names were broken. Counting members also matches the historical record, which speaks of "the average stock" and counts of breakdowns, not composites.
- Tradeoff: at eleven names each member moves breadth by about nine points, so roster changes must be annotated on the dashboard (`roster_changed_today`) and a single delisting is visible in the series.
- Review: PR #25 (contract), PR #46 (marts, reviewed by Ahrar, merged 2026-10-19).

## The eleven speculative names and the roster rules

- Recorded: 2026-10-07 (M §4); roster seeded in `dbt/seeds/basket_members.csv`
- Owner: Javier, Lane 3
- Decision: Founding roster of exactly eleven: CRWV, NBIS, IREN, APLD, WULF, CIFR, SMCI, AI, SOUN, BBAI, SPCX. Two admission tests (professionals would sell it early; valuation rests on story, not cash flow). Removal only for delisting or acquisition, ceasing to be an AI story, or durable graduation to profitability and institutional ownership. Never removed for falling. Every change dated and reasoned in `basket_members`, modeled as a slowly changing dimension so history is never recomputed under a later roster.
- Alternative considered: a larger rules-based screen (for example every US-listed name tagged AI with sales multiple above a cutoff), or using ARKK itself as the basket.
- Reason: the pattern we are instrumenting is about the names a risk-reducing professional sells first in this cycle: leveraged neoclouds, debt-funded data-center builders, retail story stocks, and the one froth thermometer (SpaceX). A screen would admit names with no retail following; ARKK is diversified beyond AI and is used instead as the external cross-check.
- Tradeoff: the basket is hand-picked and the choice is subjective by construction. Mitigations are the written criteria, the changelog, the ARKK audit flag (next entry) and the limitation recorded in M §5. See also "Roster fixed after the breaks began" below.
- Review: PR #25; eleven-name roster confirmed in the Methodology table and the seed. `basket_members_no_overlapping_spans` enforces "no name in both baskets at once."

## ARKK as the external check, 15-point disagreement threshold

- Recorded: 2026-10-08 (M §4)
- Owner: Javier, Lane 3
- Decision: ARKK enters no condition. When ARKK's drawdown and the speculative median differ by 15 percentage points or more, `basket_audit_flag` is TRUE and the standing instruction is to audit the basket before trusting a market-wide reading.
- Alternative considered: using ARKK as a twelfth member, or as the basket outright.
- Reason: ARKK is the market's own tradeable speculative-growth basket and was part of the 2021 episode, which makes it a fair outside referee for a hand-picked roster; putting it inside the basket would remove the only independent check we have.
- Tradeoff: 15 points is judgment. A smaller gap would flag constantly (ARKK holds many names outside AI); a larger one would never flag.
- Review: PR #25. First real run (see "First real reading") fired the flag with clean data, which produced the AI-specific qualifier entry below.

## Threshold calibration

- Recorded: 2026-10-07, deterioration band amended 2026-10-08 (M §2, §3)
- Owner: Javier, Lane 3
- Decision: every threshold was fixed in advance from the four historical episodes (1929, 1972, 2000, 2021) and from the Feb to May 2026 whipsaw, and is changed only with a logged reason. None was fitted to recent data.

| Threshold | Value | Origin |
| --- | --- | --- |
| Member "broken" | drawdown ≤ -25% | Deep enough that an ordinary growth-stock correction (10 to 20%) does not count; shallow enough that the 35 to 40% speculative declines of 1929, 2000 and 2021 register months before they bottom. |
| Divergence breadth | ≥ 50%, strict ≥ 70% | A majority of the basket broken is the literal reading of "the average stock" falling while the index rises. 70% marks intensity, not a different pattern; the 2021 ARK-style names were near-universally broken by May. |
| Divergence median | ≤ -15%, strict ≤ -25% | Pairs with breadth so that half the basket just past -25% and half near highs (median around -15%) still qualifies, while a basket sitting at -5% with two collapsed outliers does not. |
| S&P "near its high" | within 5% | The pattern requires the index to be hiding the breakdown; 5% is the conventional bound of noise around a record. |
| Deterioration | S&P ≤ -5%, or SPY/RSP ≤ -5% of its 126-day high, or credit at stress | Amended 2026-10-08: the original 5 to 10% band left a decline past 10% without a mega-cap break satisfying no condition at all. |
| Repricing | S&P ≤ -10% and (mega median ≤ -15% or concentration broken) | -10% is the conventional correction threshold; the mega-cap or concentration leg distinguishes "the giants are repricing" (1973-74 Nifty Fifty, 2022 mega caps) from a broad shallow dip. |
| Washout | S&P ≤ -20%, breadth ≥ 90%, credit at stress | -20% is the conventional bear-market definition; the other two legs require the whole structure to be broken at once. |
| Confirmation period | 15 consecutive trading days | Three trading weeks. Goldman's unprofitable-tech basket fell about 33% Feb to Apr 2026 then recovered 27% in May; a daily reading would have armed and gone quiet. A longer window would delay arming past the point where 2021's crack was unambiguous (May). |
| Armed expiry | 18 quiet months (378 quiet trading days) | The historical crack-to-top gap runs 6 to 12 months depending on dating choices; the expiry sits above the range because expiring just before the top is far more expensive than idling armed a few months too long. |
| Armed ceiling | 36 calendar months from armed_since | Bounds the quiet-clock suspension so a choppy market cannot make the memory immortal; no historical span from first crack to washout exceeded roughly two and a half years. |
| Credit watch / stress | HYG/IEF 3% / 6% below its 126-day high | Daily high-yield-to-Treasury ratio moves are small; 3% is judged the first clear risk-off move and 6% a genuine funding-window closure; both are judgment, fixed in advance. Credit alone can never lift the dial past Level 1 (M §3). |
| Concentration broken | SPY/RSP 5% below its 126-day high | A 5% unwind of cap-weighted over equal-weighted over six months is the mega caps giving back their refuge premium. |
| Episode exit | breadth < 30% | Hysteresis against the 50% entry so a pause in selling does not split one episode into several. |
| Young listings | first 20 days excluded from the reference high; 60 days to maturity | An IPO-pop week must never become the yardstick; a high built on a few weeks of data is noise. SPCX matured into the signal in early September 2026 under both rules. |

- Alternative considered: optimizing thresholds against the 2024 to 2026 backfill. Rejected: a threshold tuned to fit the past tells us nothing about the future, and the backfill is one cycle.
- Tradeoff: reasonable people could set every one of these differently; the defense is that they were fixed before the first run and are documented here.
- Review: PR #25 (values in the contract), PR #46 (`daily_signals_dial_consistency` and the condition-matrix fixtures assert them cell by cell).

## Benchmark is ^GSPC, not SPY

- Recorded: 2026-10-08 (C §1)
- Owner: Javier, Lane 3
- Decision: the S&P 500 distance from high is computed on ^GSPC, the price index. SPY stays in the universe only as the numerator of the concentration ratio (SPY/RSP).
- Alternative considered: SPY for everything, which would have meant one fewer symbol.
- Reason: the historical episodes are dated on the index itself, and the ETF's dividend adjustments make an adjusted-close "high" drift from the price high the record refers to. yfinance 1.1.0 serves ^GSPC with Adj Close equal to Close on every row (verified 2026-10-08), so the drawdown is a pure price drawdown.
- Tradeoff: ^GSPC is an index, not a security; it is carried in `basket_members` as a `reference_series` row with no volume.
- Review: PR #25; PR #37 (Lane 1 extractor) confirmed all 24 symbols return daily.

## A quiet month is 21 trading days

- Recorded: 2026-10-08 (C §1)
- Owner: Javier, Lane 3
- Decision: 18 quiet months equals 378 quiet trading days (18 × 21). The 36-month ceiling, by contrast, is a plain calendar comparison on `armed_since`.
- Alternative considered: counting quiet calendar months, or 252/12 = 21 days exactly versus the true average of about 20.9.
- Reason: quiet days are a count of trading days on which the dial sat below Level 3, and the clock pauses on non-quiet days, so the budget has to be in trading days; 21 is the conventional trading-days-per-month figure and makes the arithmetic auditable. The ceiling is a hard outer bound, where calendar time is the natural unit.
- Tradeoff: 378 is about two trading days longer than the true 18-month average. Immaterial at this horizon.
- Review: PR #25; `quiet_days_used` is capped at 378 in `daily_signals` and `quiet_expiry_date` is the 378th quiet day in `episodes`.

## A 0-to-5 dial with one memory bit, replacing color stages

- Recorded: 2026-10-07 (M §3)
- Owner: Javier, Lane 3
- Decision: the single output is a dial level 0 to 5, equal to the most severe level whose requirements are met today. The only memory is `is_armed` plus `armed_since`. Levels 3 and above are reachable only while armed. De-escalation happens only on explicit exits. Unarmed deterioration or repricing shows as a badge at Level 1 (off-pattern or credit-only). "Stage" is retired from system vocabulary.
- Alternative considered: the prototype's green / yellow / orange / red stages, which advanced one at a time and carried their own memory.
- Reason: stages required a recursive state machine (today's stage depends on yesterday's), which SQL over a backfill handles badly and which cannot be rebuilt idempotently. Making every condition a memoryless fact about today's prices and isolating memory into one bit let the contract dissolve the recursion: arming intervals `[held_date, disarm_date)` are computable from prices alone, and `is_armed` on any date is "some interval covers today" (C §3). It also makes the output honest: the dial says how severe today looks given what is on record, not how many steps have been climbed.
- Tradeoff: while armed, an unrelated later correction escalates the dial as if it were the sequence. Accepted and documented (M §3) in preference to a recovery disarm, which cannot be built reliably from rolling-window drawdowns.
- Review: PR #25; PR #46. The fixture scenario visits every level and every `armed_state_change` value (armed, rearmed, disarmed_quiet, disarmed_ceiling) and matches the independent oracle cell by cell.

## Validation by an independent oracle, not by inspection

- Recorded: 2026-10-15, extended 2026-10-20
- Owner: Javier, Lane 3
- Decision: the marts are tested against a second implementation of the Methodology written in plain Python with an explicit day-by-day state machine (`dbt/validation/oracle.py`), run on a synthetic seven-year scenario (`gen_scenario.py`) designed so the dial visits every level. `compare.py` diffs every column of every row.
- Alternative considered: hand-written expected values for a few dates, or trusting dbt schema tests alone.
- Reason: the SQL uses window functions and arming intervals; the oracle loops. A logic error in one is unlikely to be mirrored in the other. Hand fixtures cannot cover the armed clock's edge cases (re-arming, ceiling, partial loads).
- Tradeoff: the models are written in the dialect intersection of BigQuery and DuckDB so the oracle comparison runs locally without GCP.
- Review: ALL MATCH on all four marts, 2026-10-20; 121/121 tests on BigQuery prod the same day. The SMCI-removal case was added after Ahrar's review of #46 found `roster_changed_today` could not see removals (fixed in PR #54).

## Marts are full-rebuild tables; days_listed estimate and FRED placeholder

- Recorded: 2026-10-14 (C §3)
- Owner: Javier, Lane 3
- Decision: every mart is materialized as a table and rebuilt in full on each run, partitioned by `trade_date` and clustered by `ticker`. `days_listed` for trading days before the backfill start is estimated at 252 per 365 calendar days from `listing_date`. `fred_hy_oas` is NULL until a FRED source lands; it is never an input.
- Alternative considered: incremental models; counting `days_listed` from the first warehouse row.
- Reason: the 252-day windows make any partition depend on the prior year, so an incremental strategy would need a lookback anyway; at 24 tickers over two years the rebuild takes about two minutes and is exactly idempotent. Counting from the first warehouse row would make Microsoft look like an IPO on 2024-10-01.
- Tradeoff: the estimate is off by holidays for pre-backfill spans, which only matters for names that listed shortly before 2024-10-01 (none in the roster).
- Review: PR #46.

## Newest trading day held back while any in-force ticker is missing

- Recorded: 2026-10-18 (C §3, `int_trading_calendar`)
- Owner: Javier, Lane 3
- Decision: the newest `trade_date` in staging is excluded from the trading calendar, and so from every mart, while any in-force, already-listed ticker has no row on it. Only the newest day is held back; a gap on an older day is a real event and stays visible, with that member not counting as valid data that day.
- Alternative considered: computing the day on whatever arrived, then correcting on the next run.
- Reason: the extractor can fire before the provider has served every ticker; a partial day would move breadth by a member or two and the dial could flicker for one evening, which the Methodology forbids.
- Tradeoff: the dashboard's newest date can trail the calendar by one session; Lane 4's freshness notice accounts for this.
- Review: PR #46; Lane 2's freshness checks (PR #59) sit upstream.

## `intermediate.int_daily_conditions` as a helper table outside the contract

- Recorded: 2026-10-20
- Owner: Javier, Lane 3
- Decision: the per-day condition flags are materialized as a table in the `intermediate` dataset rather than as an ephemeral CTE.
- Alternative considered: keep it ephemeral; fold it into `daily_signals`.
- Reason: BigQuery re-evaluated the ephemeral CTE once per reference; `episodes` alone took 186 s. As a table, `episodes` builds in 16 s and the whole prod build in 116 s.
- Tradeoff: one dataset not in the schema contract; the DAG service account needs project-level dataset-create rights for `intermediate` (noted on PR #48). The contract's five tables are unchanged.
- Review: PR #54, reviewed by Ahrar, merged 2026-10-20.

## First real reading and the AI-specific qualifier

- Recorded: 2026-10-20, amendment adopted 2026-10-25 (M §4)
- Owner: Javier, Lane 3; dashboard wording with Yuanhao, Lane 4
- Finding: the first production reading (2026-10-15) was Level 2 DIVERGENCE, armed since 2025-10-22, breadth 0.91, S&P about 1% from its high, credit normal. `basket_audit_flag` was TRUE with clean data: ARKK sat near its highs while ten of eleven members were broken. The mega-cap basket split (ORCL -56%, AVGO -28%, mega median -10.3%). The break is specific to the AI speculative tier; it is not a market-wide speculative unwind.
- Decision: when the audit flag is TRUE and the data is clean (every in-force member priced on the day), the dial is not discounted. The dashboard shows the qualifier "AI-specific: the broader speculative market (ARKK) does not confirm this break," and the reading is used for the AI tier only. The dial, badge and armed state are unchanged; the qualifier is display text derived from `basket_audit_flag`. This resolves the open item in Lane 4's "Data and display boundary" entry above and unblocks #51.
- Alternative considered: treating the flag as a reason to distrust the reading (the original standing instruction); adding ARKK as a condition.
- Reason: the audit flag exists to catch a mis-built basket. The audit was done and the basket is right; the disagreement is information about the market, which is that the rotation has started in AI and nowhere else yet. Adding ARKK to a condition would make the system a general speculative-growth monitor, which is a different project.
- Tradeoff: a sector-specific break is a weaker precedent than the 1929, 2000 and 2021 episodes, in which the whole speculative tier cracked. The qualifier says so.
- Review: to be merged with this entry; Lane 4 to adopt the wording in #51.

## Roster fixed after the breaks began (limitation) and Phase 2 backtest

- Recorded: 2026-10-20 (M §5)
- Owner: Javier, Lane 3
- Decision: record as a limitation that the founding roster was chosen in October 2026, after most of its members had already broken, so the backfilled armed history from 2024-10-01 is informed by hindsight and should be read as an illustration of the mechanics, not as an out-of-sample test. Phase 2 candidate: a rules-based roster as of 2024-10-01 (screened on data available that day) and a backtest of the dial against it.
- Alternative considered: silently presenting the backfill as a track record.
- Reason: the Methodology's defense of the thresholds is that they were fixed in advance; the same standard has to apply to the roster, and it does not yet.
- Tradeoff: the Phase 1 story is weaker ("here is the pattern, live, with the mechanics proven on synthetic data") and more honest.
- Review: M §5 amended in this PR.

## Accepted Lane 1 limitations for Phase 1

- Recorded: 2026-10-20
- Owner: Javier, Lane 3, with Kean, Lane 1
- Decision: the extractor's ticker list is hard-coded (not read from `basket_members`), and there is no index-level fallback if ^GSPC is unavailable from both providers. Both accepted for Phase 1. The two-year backfill horizon is filed as an issue for Lane 1.
- Reason: roster changes are rare and logged, so a code change per change is acceptable this term; all 24 symbols returned every trading day since 2026-09-24 when verified on 2026-10-08.
- Review: PR #48 (Javier approved with notes on merge order and `intermediate` dataset rights).
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

## Public dashboard access

- Recorded: 2026-10-27
- Owner: Chloe, Lane 5
- Decision: The Cloud Run dashboard is public; anyone with the link can view it without logging in.
- Alternative considered: Identity-Aware Proxy limited to BU accounts, as first planned in the Lane 4 deployment notes.
- Reason: the page shows only public market data and our derived signal, and the professor and peers need to open it without setup.
- Safeguard: the service runs as `dashboard-runtime`, which can read the `marts` dataset and nothing else and cannot write anywhere, so public access cannot change data. `max-instances=2` and the $50 budget alert bound cost.

## MLflow hosting

- Recorded: 2026-11-13
- Owner: Chloe, Lane 5
- Decision: The MLflow tracking server runs on Cloud Run (scales to zero, at most one instance). Run metadata is a SQLite file in a GCS bucket mounted into the container; artifacts go to the same bucket. The service is private: only granted members and the `airflow-pipeline` account can call it. Defined in `terraform/mlflow.tf`.
- Alternative considered: Cloud SQL (PostgreSQL) as the metadata store, the standard production setup.
- Reason: Cloud SQL bills for every hour it runs, even when idle, against a $50 project budget, while our load is one weekly training job and a few people browsing. The bucket setup costs close to nothing when idle.
- Tradeoff: SQLite on a bucket mount supports one writer only, so parallel training jobs could fail with "database is locked", and the first request after idle has a cold start. The bucket is versioned (old versions kept 7 days) so a damaged database can be restored. If we need parallel writers, move the metadata to Cloud SQL; the server image and artifact bucket stay the same.
- Check: tested locally on Nov 13 with MLflow 2.22.0 (SQLite metadata, artifacts proxied through the server); not yet deployed.
## Phase 2 rules (Lane 3)

These entries were written before any universe ticker was selected and before any model was trained. "C3 §n" points to `docs/schema_contract_v0.3.md`. The numbering R1 to R8 is what the contract's trace tags refer to. Javier took decisions R1, R3, R4 and R8 on 2026-11-16 from options prepared with Claude; the options and reasons are below.

## R1 · The universe is drawn by rule from AI-named ETFs

- Recorded: 2026-11-16
- Owner: Javier, Lane 3
- Decision: The Phase 2 universe is the union of the holdings of every ETF that meets all of these on the snapshot date: listed on a US exchange; "AI" or "Artificial Intelligence" in the fund's name; net assets of at least $1 billion as published by the issuer; not leveraged, inverse, single-stock or option-income. Holdings are taken from each issuer's own holdings file. A holding enters the universe when it is a common stock or ADR trading on NYSE or Nasdaq, closed above $2, averaged at least $5 million a day in dollar volume over the prior 60 trading days, and has at least 60 trading days of history. Cash, derivatives and private positions are dropped. When two share classes of one company are held, the one with the higher dollar volume is kept.
- Snapshot date: the first trading day after the pull request carrying this entry is merged to main. The date, the qualifying ETFs with their net assets, and the holdings files are committed with the seed, so the order "rule first, list second" can be checked from git history.
- Expected to qualify (checked on fund-tracker sites on Nov 16, to be confirmed from issuer figures on the snapshot date): AIQ, BAI, ARTY, BOTZ, CHAT, IGPT, AGIX, IVES. The list is whatever the rule returns that day.
- Alternatives considered: (a) AIQ and ARTY only, the two largest index funds: cleanest, but they share many holdings and may leave too few names; (b) the same rule at $500 million, which adds robotics funds whose holdings are industrial companies; (c) index-tracking funds only, which avoids manager discretion but is a second judgment call on top of the rule.
- Reason: a one-sentence mechanical rule means nobody on the team chooses a fund or a stock. That is the point of Phase 2: testing whether our signal depends on our own picks.
- Tradeoff: three of the expected funds are actively managed, so part of the universe is what managers like today. The price and liquidity conditions are also re-checked on every weekly date (C3 §2, `is_model_eligible`), so a name that only became liquid recently does not contribute old rows.
- Refresh: none during Phase 2. A later refresh is a new logged decision with a new snapshot date.

## R2 · Our 11 never train the model and never feed its features

- Recorded: 2026-11-16
- Owner: Javier, Lane 3
- Decision: Any ticker with a speculative span in `basket_members` is excluded from `universe_members` by a seed test, from training, validation and test rows by `role`, and from `universe_breadth`. Our 11 are scored by the finished model as out-of-sample targets. The official dial level is not a model input.
- Reason: several of our names are held by AI ETFs, so the ETF rule alone would pull them into training. The roster was hand-picked in October 2026 after most names had broken (M §5); a model that saw them, directly or through a basket-level feature, would learn our picks.
- Tradeoff: megacap members of our Phase 1 roster (NVDA, MSFT and others) do enter the universe when an ETF holds them. They were chosen as the market's largest AI names, a rule anyone would reproduce, so they are treated as ordinary universe members.

## R3 · The label: a 20% fall at any point in the next 60 trading days

- Recorded: 2026-11-16
- Owner: Javier, Lane 3
- Decision: For a stock on a weekly date, the label is 1 if its lowest adjusted close over the next 60 trading days is at least 20% below that date's adjusted close, otherwise 0. The fall is absolute, with no adjustment for the market. The label is empty until 60 forward trading days exist.
- Alternatives considered: other thresholds (15%, 25%, 30%) and horizons (20 or 120 days); the close at the end of the window in place of the lowest close; a fall measured relative to the S&P 500.
- Reason: the team agreed this label in PR #68 and the API field is built on it. The lowest close counts a stock that fell 25% and recovered, which is what a risk warning should count and how the dial already reads drawdowns. An absolute fall is what a holder experiences and is easy to explain.
- Pre-registered check: before any model is trained, the share of 1s is computed on training rows only. If it is between 10% and 40%, the label stands. Above 40%, the threshold moves to 25%; below 10%, to 15%. The check is run once more on the new threshold and the result is logged here either way. No other change to the label is allowed after results are seen.
- Tradeoff: an absolute label lets the model score well by recognizing market-wide sell-offs, and the training period has one large one (2022). The evaluation reports results by year for that reason (R7).

## R4 · One time split, fixed in advance

- Recorded: 2026-11-16
- Owner: Javier, Lane 3
- Decision: Train on weekly dates 2021-01-08 through 2024-06-28. Validate on 2024-10-04 through 2025-06-27. Test on 2025-10-03 through the last date with a final label (about 2026-08-21 at freeze). The weeks between sets are unused, so no label window in one set overlaps the next set (at least 60 trading days). Validation is for tuning and for choosing between models. The test period is scored once.
- Alternatives considered: a longer test period starting in 2025 with training ending in 2023; walk-forward evaluation with several folds.
- Reason: training keeps the 2022 sell-off, the only bear market in the data. The test period is the stretch in which our dial has been armed, which is the period the project is about. Walk-forward is more rigorous and is listed as a next step; it does not fit the time left.
- Tradeoff: the test period holds about 46 weeks, fewer than four non-overlapping 60-day windows. Every test metric is reported with a block-bootstrap interval and the intervals will be wide.
- Note: training starts in January 2021 because the 252-day window needs a year of the January 2020 backfill. Weekly retraining in production uses all labeled data; this split governs the evaluation report only.

## R5 · Twelve features, all available for the whole training period

- Recorded: 2026-11-16
- Owner: Javier, Lane 3
- Decision: The model inputs are the twelve columns listed in C3 §2 under `weekly_features`: drawdown from the 252-day high; 20, 60 and 120-day returns; 60-day volatility; volume against its 60-day average; 120-day beta to the S&P 500 and to ARKK; days listed (capped at five years); S&P distance from its high; credit ratio distance from its high; breadth of the universe. A row is scored only with 126 trading days of history and every input present.
- Change from the proposal: the official dial level is removed. It exists only from late 2024 and is computed from our 11, so it could not cover 2021 to 2024 rows and would break R2.
- Reason: a feature missing for most of the training period teaches the model nothing reliable, and every input must be computable from prices dated on or before the row's date.
- Tradeoff: `universe_breadth` is computed over today's universe, so in past years it describes the stocks that later became ETF holdings. Stated as a known limit (R7).

## R6 · How the model is judged, and which model is served

- Recorded: 2026-11-16
- Owner: Javier, Lane 3
- Decision: Four models are compared: drawdown only, volatility only, logistic regression, boosted trees. Metrics are AUC, precision in the top 10% of scores, Brier score and a calibration table, on the validation and test periods, each next to the base rate. Intervals are 90%, from a block bootstrap that resamples whole weeks in blocks of 13 (about 60 trading days), 1,000 times. The better of the two ML models on validation AUC is the candidate. It "beats the baselines" only if, on the test period, the bootstrap interval of its AUC minus the best baseline's AUC lies above zero. If it does, it is served; otherwise the best baseline is served and the report says so.
- Reason: weekly rows of one stock share most of their label window, and all stocks share the same weeks, so rows are far from independent. Resampling whole blocks of weeks keeps that dependence in the interval. Fixing the pass rule now removes the temptation to pick a favorable metric later.
- Tradeoff: with a short test period the rule is strict and the likely honest outcome is "not distinguishable from the baselines". The proposal already accepts that as a valid result.

## R7 · Known limits: what is measured and what is only stated

- Recorded: 2026-11-16
- Owner: Javier, Lane 3
- Measured and reported next to the results: (1) regime dependence, by reporting the base rate and AUC by calendar year and the share of training positives that fall in 2022; (2) hindsight in the universe, by repeating the test-period evaluation on names that already had five years of history in January 2021, a group that today's ETF fashion selected less; (3) our 11 against the universe, as the distribution of their percentile ranks.
- Stated, with direction of bias, because we cannot measure it: survivorship. Stocks that were delisted or dropped from ETFs before the snapshot are absent, so past falls are understated and the base rate is biased down. Past ETF holdings would be needed to measure this and are not available to us.

## R8 · Training engine: BigQuery ML (decided)

- Recorded: 2026-11-16
- Owner: Javier, Lane 3, with Ahrar (Lane 2) and Chloe (Lane 5); open under #94 until both agree
- Proposal: train and score in BigQuery ML (`LOGISTIC_REG`, `BOOSTED_TREE_CLASSIFIER`) from dbt, with a short Python step in the weekly Airflow task that logs parameters, metrics, the snapshot date and the model version to MLflow. The baselines are single-feature logistic regressions so all four models go through the same path. The evaluation in R6 runs in Python on `model_predictions`.
- Alternative considered: scikit-learn in a Python job, which logs to MLflow natively but needs its own container, data export and scheduling.
- Reason: the data never leaves the warehouse, Lane 2 already owns dbt, and the course covers BigQuery ML. The tables are small (roughly 100 to 150 stocks × 300 weeks), so cost is negligible; Lane 5 confirms under #90.
- Decided: 2026-11-25, closed under #94. Lane 2 builds the Phase 2 models in BigQuery ML (#103).

## Phase 2 rules: amendments after review (Nov 22)

- Recorded: 2026-11-22
- Owner: Javier, Lane 3
- Calendar floor (C3 §1 item 3): the Phase 1 calendar is floored at 2023-10-02, not 2024-10-01. Lane 1 found on Nov 17 that prod `raw.prices_raw` starts on 2023-10-02 and that the year before 2024-10-01 fills the 252-day reference window, so the earlier floor would itself have changed `daily_drawdowns` and `daily_signals`. The floor is the dbt var `phase1_cal_floor` in `int_trading_calendar`, merged with the contract and before the backfill. Acceptance is unchanged: the four Phase 1 marts are row-for-row identical before and after the backfill (Lane 1 checks under #70).
- Breadth and eligibility (R5): `universe_breadth` is computed over screen-eligible universe rows (history, price and liquidity screen plus a non-NULL drawdown_252) instead of model-eligible rows. The draft defined breadth on model eligibility and model eligibility on breadth being present, which is circular. Lane 4 flagged it on Nov 18.
- `trained_at` added to `model_predictions`, `model_scores` and `model_evaluation`, one value per model_version, at Lane 4's request.
- No rule changed: universe, label, split and features stay as recorded in R1 to R6.

## Public model API

- Recorded: 2026-11-13
- Owner: Chloe, Lane 5
- Decision: The model API (`model-api` on Cloud Run) is public; anyone with the URL can call it without logging in. It serves the latest weekly scores from `marts.model_scores` and reads a CSV of dummy rows until that table exists. Defined in `terraform/api.tf`.
- Alternative considered: a private service like MLflow, with each caller sending an identity token.
- Reason: the Phase 2 brief has reviewers call the API during evaluation, and the scores are derived from public market data.
- Safeguard: the service runs as `model-api`, which can run queries and read the `marts` dataset only, with no write access anywhere, the same limits as `dashboard-runtime`. At most 2 instances, and results are cached for 10 minutes so repeated calls do not re-query BigQuery. Every response says whether it came from dummy data or the warehouse.

## R1 applied: universe snapshot of 2026-11-23

- Recorded: 2026-11-24
- Owner: Javier, Lane 3
- Result: six ETFs qualify (BAI, AIQ, ARTY, BOTZ, CHAT, IGPT) and 141 tickers enter `universe_members` (file in `docs/universe_snapshot_2026-11-23/`, seeded by Lane 2 in #74). AGIX, IVES and ALAI are under $1B on issuer figures. Evidence and the screen are in `docs/universe_snapshot_2026-11-23/`; the seed is rebuilt by `scripts/build_universe_snapshot.py`.
- Clarification: "net assets on the snapshot date" means as of the Nov 23 close for every fund. Invesco had published only its Nov 20 figure ($985.4M) on Nov 23; at the Nov 23 close IGPT was about $1.10B. Decided before any model result exists. Confirmed Nov 25 from Invesco's NAV history: $1.104B on Nov 23 ($74.259056 x 14.87M shares).
- Clarifications of the holdings rule: a company held only through a non-US line does not enter; NYSE American is not NYSE; foreign tickers that collide with a different US company on Yahoo are dropped.
- Change: the issuer holdings files are not committed, because Global X and BlackRock prohibit redistribution. Source URLs, as-of dates and per-ticker fund membership are committed instead. The order "rule first, list second" stays checkable from git history.
- No rule changed.

## Phase 1 marts after the 2020 backfill: dividend re-adjustment accepted

- Recorded: 2026-11-25
- Owner: Javier, Lane 3; evidence by Kean, Lane 1 (#70)
- Context: C3 §1 item 3 asked that the four Phase 1 marts be row-for-row identical before and after the January 2020 backfill. The purpose was to prove the calendar floor and the larger load do not change Phase 1 logic.
- Finding: episodes identical; no `is_broken`, `is_signal_eligible`, `dial_level` or `is_armed` value changed on any day. Every difference traces to yfinance re-adjusting `adj_close` for dividends paid since the October load (largest drawdown change 0.51 points, all in dividend payers). One visible effect: `credit_status` went watch to normal on 2026-11-02, 11-05 and 11-06, where `credit_distance` moved from -3.10% to -2.97% across the -3% line after HYG and IEF paid early-November dividends. The dial stayed Level 3, armed, on all three days.
- Decision: accepted. The test is read as "identical given the same adjusted prices"; a vendor re-adjustment is not a logic change, and it would happen on any re-pull. The re-adjusted series is the correct one, so the new values stand.
- Consequence: any full re-pull can move old drawdowns in the third or fourth decimal for dividend payers, and a value sitting on a threshold can flip. The Lane 1 README (#106) says so.

