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
