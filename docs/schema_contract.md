# Schema contract v0.2 (draft for comment)

BA882 · AI Bubble Early-Warning System · Lane 3 · circulated Monday Oct 12, 2026 · comments from Lanes 1, 2 and 4 by Wednesday Oct 14 · frozen Thursday Oct 15.

This document is Methodology section 6 translated into tables. Every column points at the paragraph it implements, so a modeling dispute resolves by rereading that paragraph. The machine-readable version of this same contract is the dbt YAML in `dbt/` (sources.yml, seeds/schema.yml, models/marts/marts.yml, tests/); the YAML is what the build enforces, this page is what people read. If they ever disagree, fix both in the same pull request.

## 1. Conventions every table inherits

1. **Names.** Tables exactly as the Methodology names them. Columns snake_case. The day column is `trade_date` (DATE) everywhere; `ticker` is the uppercase yfinance symbol.
2. **Grain and key.** prices_raw and daily_drawdowns: one row per (trade_date, ticker). daily_signals and credit_daily: one row per trade_date. basket_members: one row per (ticker, added_date), a type 2 slowly changing dimension. episodes: one row per span, keyed by episode_id.
3. **Types.** FLOAT64 for prices, ratios and drawdowns; INT64 for counts and the dial level; BOOL for flags; STRING for enumerations, each with an accepted-values test; TIMESTAMP (UTC) for audit columns.
4. **Sign convention.** Every drawdown and distance from high is `price / high - 1`. A name 25% below its high reads -0.25; "broken" is `drawdown <= -0.25`; "within 5% of its high" is `distance > -0.05`. One convention for members, the S&P, the concentration ratio and the credit ratio.
5. **Price.** Adjusted close is the only price any math reads. Raw close is kept in prices_raw for audit. An unadjusted series would print a fake crash on a split.
6. **Windows are trading days, never calendar days.** 252 for the reference high, 126 for the concentration and credit highs, 20 for the IPO exclusion, 60 for maturity, 15 for the confirmation period. A trading day is any date on which ^GSPC has a row. A member with no price on a trading day is not "valid data" that day; nothing is forward-filled.
7. **Nulls mean "the Methodology says there is no value yet."** reference_high and drawdown are NULL during a listing's first 20 trading days; breadth is NULL when no member is valid; armed_since is NULL when not armed. Everything else is NOT NULL and tested as such.
8. **Partitioning.** Every table is partitioned by trade_date (episodes by start_date) and clustered by ticker where a ticker column exists.
9. **All 22 symbols live in basket_members**, with basket in {speculative, megacap, benchmark, reference}. The extractor reads its ticker list from that table, so "what did we track on date X" is reproducible, and the section 4 roster rules apply to the two baskets that matter.
10. **Idempotency.** (trade_date, ticker) is unique in prices_raw; a re-run merges on it and records `source` and `ingested_at`.

Two decisions taken on Oct 8 while drafting, to be logged in the decision log: the **benchmark is ^GSPC**, the price-only index (SPY stays in the universe for the concentration ratio only); a **quiet month is 21 trading days**, so the armed expiry budget is 378 quiet days and the 36-month ceiling is a plain calendar comparison on armed_since.

## 2. The tables

### prices_raw (source, dataset `raw`, owner Lane 1)

| Column | Type | Null | Meaning | Trace |
|---|---|---|---|---|
| trade_date | DATE | no | Exchange trading date; partition column | C1, C8 |
| ticker | STRING | no | yfinance symbol; must exist in basket_members | C1, C9 |
| open | FLOAT64 | yes | Unadjusted intraday high/low/open; audit only | audit |
| high | FLOAT64 | yes | | audit |
| low | FLOAT64 | yes | | audit |
| close | FLOAT64 | no | Unadjusted close; audit only | C5 |
| adj_close | FLOAT64 | no | Adjusted close; the only price downstream math reads | M§2, C5 |
| volume | INT64 | yes | NULL for index symbols | audit |
| source | STRING | no | yfinance, alphavantage, tiingo | Lane 1 fallback |
| ingested_at | TIMESTAMP | no | Load time; freshness column | C3 |
| run_id | STRING | yes | Airflow run that wrote the row; NULL for backfill | observability |

Tests: unique (trade_date, ticker); adj_close > 0; source in list; freshness warn at 30 h, error at 54 h.

### basket_members (dbt seed, owner Lane 2, content owner Lane 3)

| Column | Type | Null | Meaning | Trace |
|---|---|---|---|---|
| ticker | STRING | no | | |
| company_name | STRING | no | Display name for the ticker table | L4 |
| basket | STRING | no | speculative, megacap, benchmark, reference | M§2 |
| profile | STRING | yes | One-line rationale from the section 4 table | M§4 |
| listing_date | DATE | no | First trading day of the symbol; drives the 20-day and 60-day rules. Stored explicitly because the two-year backfill would make every old name look newly listed | M§2 |
| added_date | DATE | no | First trade_date the span is in force (inclusive); part of the key | M§4 |
| removed_date | DATE | yes | First trade_date the span is no longer in force (exclusive); NULL = current | M§4 |
| added_reason | STRING | no | founding_roster, new_listing, promotion_to_megacap, reference_series | M§4 |
| removed_reason | STRING | yes | delisting_or_acquisition, no_longer_ai_story, graduation, promotion_to_megacap. "Fell" is deliberately not a value | M§4 |
| notes | STRING | yes | e.g. the PR that logged the change | |

Tests: unique (ticker, added_date); no overlapping spans per ticker (which also enforces "no name in both baskets at once"); reasons in list. The founding roster of 24 rows (11 + 7 + ^GSPC + 5 reference) ships as `dbt/seeds/basket_members.csv`; SPCX's listing date is June 12, 2026 (confirmed Oct 8).

### daily_drawdowns (mart, one row per trade_date × tracked ticker)

| Column | Type | Null | Meaning | Trace |
|---|---|---|---|---|
| trade_date | DATE | no | Partition column | C1 |
| ticker | STRING | no | Clustering column | C1 |
| basket | STRING | no | Basket whose span covers trade_date; a ticker with no span in force has no row | M§4 |
| adj_close | FLOAT64 | no | | C5 |
| days_listed | INT64 | no | Trading days since listing_date, inclusive (1 on listing day), on the benchmark calendar | M§2 |
| reference_window_days | INT64 | no | Trading days that fed reference_high: trailing 252 including today, minus days with days_listed <= 20. 0 while days_listed <= 20 | M§2, M§6 |
| reference_high | FLOAT64 | yes | Max adj_close over the window; NULL while window is 0 | M§2 |
| drawdown | FLOAT64 | yes | adj_close / reference_high - 1 | M§2, C4 |
| is_mature | BOOL | no | days_listed >= 60 | M§2 |
| is_signal_eligible | BOOL | no | is_mature AND drawdown not NULL AND basket in (speculative, megacap). The breadth denominator and the median population | M§2 |
| is_broken | BOOL | yes | drawdown <= -0.25; NULL when drawdown is NULL | M§2 |
| return_6m | FLOAT64 | yes | adj_close / adj_close 126 days earlier - 1. Not a signal input; the dashboard ticker table shows it and no math lives in the dashboard | L4, M§6 |
| computed_at | TIMESTAMP | no | | |

Tests: unique key; drawdown in [-1, 0]; the young-listing invariants as one singular test (NULLs exactly while days_listed <= 20, maturity exactly at 60, is_broken agrees with drawdown).

### credit_daily (mart, one row per trade_date)

| Column | Type | Null | Meaning | Trace |
|---|---|---|---|---|
| trade_date | DATE | no | | |
| hyg_adj_close | FLOAT64 | no | HYG adjusted close | M§2 |
| ief_adj_close | FLOAT64 | no | IEF adjusted close | M§2 |
| credit_ratio | FLOAT64 | no | HYG / IEF | M§2 |
| ratio_window_days | INT64 | no | Days that fed the high (< 126 only at backfill start) | |
| ratio_high_126 | FLOAT64 | no | Max ratio over trailing 126 days including today | M§2 |
| credit_distance | FLOAT64 | no | ratio / high - 1 | M§2, C4 |
| credit_status | STRING | no | normal (> -0.03), watch (<= -0.03), stress (<= -0.06) | M§2, M§3 |
| fred_hy_oas | FLOAT64 | yes | ICE BofA US HY OAS (FRED BAMLH0A0HYM2), the named cross-check; NULL when unpublished; never an input | M§2 |
| computed_at | TIMESTAMP | no | | |

### daily_signals (mart, one row per trade_date; the one-SELECT verdict)

Group math:

| Column | Type | Null | Meaning | Trace |
|---|---|---|---|---|
| spec_members_in_force | INT64 | no | Speculative spans covering today with listing_date <= today | M§4 |
| spec_members_valid | INT64 | no | Of those, is_signal_eligible | M§2 |
| spec_members_broken | INT64 | no | Of the valid, is_broken | M§2 |
| breadth | FLOAT64 | yes | broken / valid; NULL when valid = 0 | M§2 |
| spec_median_drawdown | FLOAT64 | yes | Median over valid speculative members | M§2 |
| roster_changed_today | BOOL | no | Any speculative or megacap span starts or ends today; the dashboard annotates these dates | M§4, L4 |
| mega_members_valid | INT64 | no | | |
| mega_median_drawdown | FLOAT64 | yes | Repricing input | M§2 |
| spx_adj_close | FLOAT64 | no | ^GSPC adjusted close | M§2 |
| spx_reference_high | FLOAT64 | no | ^GSPC max adj_close over the trailing 252 trading days including today | M§2 |
| spx_distance | FLOAT64 | no | spx_adj_close / spx_reference_high - 1 | M§2, C4 |
| concentration_ratio | FLOAT64 | no | SPY adj_close / RSP adj_close | M§2 |
| concentration_high_126 | FLOAT64 | no | Max ratio over the trailing 126 trading days including today | M§2 |
| concentration_distance | FLOAT64 | no | concentration_ratio / concentration_high_126 - 1 | M§2, C4 |
| is_concentration_broken | BOOL | no | concentration_distance <= -0.05 | M§2 |
| credit_distance | FLOAT64 | no | Copied from credit_daily | M§2 |
| credit_status | STRING | no | Copied from credit_daily: normal, watch, stress | M§2 |
| arkk_drawdown | FLOAT64 | yes | External check; in no condition | M§4 |
| basket_audit_flag | BOOL | no | abs(arkk_drawdown - spec_median_drawdown) >= 0.15, the 15-point threshold written into Methodology section 4 on Oct 8 | M§4 |

Conditions (all BOOL, NOT NULL, memoryless):

| Column | Definition | Trace |
|---|---|---|
| cond_divergence | breadth >= 0.50 AND spec_median_drawdown <= -0.15 AND spx_distance > -0.05; FALSE when breadth is NULL | M§2 matrix |
| cond_divergence_strict | 0.70 / -0.25 / same S&P leg | M§2 |
| det_spx_band | spx_distance <= -0.05 (at least 5% below its high; Methodology amended Oct 8) | M§2 matrix |
| det_concentration | is_concentration_broken | M§2 matrix |
| det_credit_stress | credit_status = 'stress' | M§2 matrix |
| cond_deterioration | any of the three det_ legs | M§2 matrix |
| cond_repricing | spx_distance <= -0.10 AND (mega_median_drawdown <= -0.15 OR is_concentration_broken) | M§2 matrix |
| cond_washout | spx_distance <= -0.20 AND breadth >= 0.90 AND credit_status = 'stress' | M§2 matrix |

Memory:

| Column | Type | Null | Meaning | Trace |
|---|---|---|---|---|
| divergence_run_days | INT64 | no | Consecutive days ending today with cond_divergence TRUE; 0 if FALSE today | M§3 |
| is_held_today | BOOL | no | divergence_run_days >= 15 | M§3 |
| episode_id | STRING | yes | Open episode covering today | M§3 |
| is_quiet_day | BOOL | no | NOT (deterioration OR repricing OR washout). See section 3 for why this column makes the clock computable | M§3 |
| is_armed | BOOL | no | Some held episode's arming interval [held_date, disarm_date) covers today | M§3 |
| armed_since | DATE | yes | start_date of the most recent such episode | M§3 |
| armed_episode_id | STRING | yes | | |
| quiet_days_used | INT64 | yes | Quiet days from armed_since through today, 0 to 378; NULL when not armed | M§3 |
| armed_ceiling_date | DATE | yes | armed_since + 36 months | M§3 |
| armed_state_change | STRING | yes | armed, rearmed, disarmed_quiet, disarmed_ceiling on the day it happens | M§3, L4 |

Output:

| Column | Type | Null | Meaning | Trace |
|---|---|---|---|---|
| dial_level | INT64 | no | Top-down: 5 if washout; 4 if armed AND repricing; 3 if armed AND deterioration; 2 if armed AND spx_distance > -0.05; 1 if divergence OR credit watch/stress OR armed OR deterioration OR repricing; else 0 | M§3 |
| dial_label | STRING | no | CALM, STRAIN, DIVERGENCE, TOPPING, REPRICING, WASHOUT | M§3 |
| badge | STRING | yes | off_pattern when unarmed and an equity leg (det_spx_band, det_concentration, repricing, washout) is TRUE; credit_only when unarmed, credit stress, and no equity leg; off_pattern wins ties | M§3 |
| dial_explanation | STRING | no | One templated sentence from a dbt macro; the verdict card renders it verbatim | L4 |
| computed_at | TIMESTAMP | no | | |

### episodes (mart, rebuilt each run, one row per divergence span)

| Column | Type | Null | Meaning | Trace |
|---|---|---|---|---|
| episode_id | STRING | no | 'EP-' + start_date | |
| start_date | DATE | no | First day cond_divergence TRUE | M§3 |
| end_date | DATE | yes | Last day inside the span; the first later day with breadth < 0.30 closes it and is excluded. NULL while open | M§3 |
| is_open | BOOL | no | | |
| trading_days | INT64 | no | Trading days inside the span | M§3 |
| divergence_days | INT64 | no | Days inside the span with cond_divergence TRUE | M§3 |
| max_divergence_run | INT64 | no | Longest consecutive run of cond_divergence inside the span | M§3 |
| is_held | BOOL | no | max_divergence_run >= 15 | M§3 |
| held_date | DATE | yes | The 15th consecutive day: the arming day | M§3 |
| max_breadth | FLOAT64 | no | Highest breadth inside the span | M§3 |
| min_spec_median_drawdown | FLOAT64 | no | Deepest speculative median drawdown inside the span | M§3 |
| strict_days | INT64 | no | Days the strict form held | M§2 |
| armed_since | DATE | yes | = start_date when held | M§3 |
| armed_ceiling_date | DATE | yes | armed_since + 36 months | M§3 |
| quiet_expiry_date | DATE | yes | Day the 378th quiet day since armed_since occurred | M§3 |
| disarm_date | DATE | yes | Day after quiet_expiry_date, or first trading day >= ceiling, whichever is first | M§3 |
| disarm_reason | STRING | yes | quiet_expiry, ceiling | M§3 |
| computed_at | TIMESTAMP | no | | |

## 3. Hard cases the contract was checked against

**Young listings.** Two rules, two columns. `days_listed` is counted from `listing_date` on the benchmark calendar, not from the first backfilled row, which is why `listing_date` lives in basket_members; without it the backfill start would make Microsoft look like an IPO. The 20-day exclusion is expressed as `reference_window_days` and a NULL `reference_high`; the 60-day gate is `is_mature`. The singular test `daily_drawdowns_young_listing_rules` asserts both exactly. SPCX, listed June 2026, matured into the signal in early September under both rules, as the Methodology states; the fixtures will replay that.

**Roster changes.** Breadth on a date counts only spans that cover the date (`added_date <= trade_date < removed_date`) and only tickers already listed. Historical rows are never recomputed under a later roster because daily_drawdowns carries `basket` as of that date. `roster_changed_today` gives the dashboard its annotation without a join. A name removed for falling is unrepresentable: `removed_reason` has no such value.

**Episodes.** Gaps and islands on `cond_divergence`, closed only by `breadth < 0.30`, so a pause in the selling does not split a span. `held_date` is the 15th consecutive divergence day and is the arming event. The table is rebuilt in full each run because an open span's row changes daily.

**The armed clock, and why no recursive state machine is needed.** Read literally, today's dial depends on armed, and armed's expiry depends on how many past days were quiet (dial below 3), which depends on past dials: sequential state, which plain SQL handles badly. The contract dissolves this. While armed, the dial is at Level 3 or above exactly when deterioration, repricing or washout is TRUE, and those three are memoryless facts about prices. So "quiet day" is itself memoryless (`is_quiet_day`), the 378th quiet day after any `armed_since` is a window count, each held episode gets a fixed arming interval `[held_date, disarm_date)` computable from prices alone, and `is_armed` on any date is "some interval covers today." Re-arming is simply a newer interval; the 36-month ceiling is a date comparison. Every column is computable with window functions over daily_drawdowns and credit_daily, fully backfillable in one `dbt run`, and testable with fixtures.

**Idempotency and backfill.** Marts are `insert_overwrite` by trade_date partition, so re-running a date replaces exactly that date. The two-year backfill from 2024-10-01 runs the same models with a wider date range.

## 4. Coverage check: condition matrix and verdict cards

Every cell of the Methodology's condition matrix maps to one column: speculative column to `breadth` and `spec_median_drawdown`; mega-cap column to `mega_median_drawdown`; S&P column to `spx_distance`; concentration column to `is_concentration_broken`; credit column to `credit_status`. Each "Not used" cell corresponds to an input that the condition's definition simply omits, so a fixture can assert the cell by flipping that input and checking the flag does not move.

Lane 4's verdict cards and charts: dial level and label, explanation sentence, badge, armed-since and credit status are all single columns of today's daily_signals row; the breadth-versus-S&P chart is `breadth` and `spx_distance` over time; member drawdowns and the 6-month return come from daily_drawdowns (`drawdown`, `return_6m`, `is_broken`, `company_name` via basket_members); the dial history strip is `dial_level` over time with `armed_state_change` and `roster_changed_today` as annotations. Nothing on the dashboard requires arithmetic.

## 5. Open items for the Oct 15 freeze

1. **Lane 1 (one confirmed, one open).** yfinance 1.1.0 serves ^GSPC with Adj Close equal to Close on every row, and all 24 symbols return every trading day since Sept 24 (verified Oct 8). FRED BAMLH0A0HYM2 confirmed in scope. Still open: whether the fallback provider (Alpha Vantage or Tiingo) can serve the index symbol, or whether ^GSPC falls back to SPY's close on a Yahoo outage.
2. **Lane 2 (one decided, one for Ahrar).** basket_members is a dbt seed (decided Oct 8): the CSV lives in the repo, every roster change is a pull request, and git carries the date, reason and reviewer the Methodology requires. Where the singular tests live, one shared `tests/` folder or a subfolder per lane, is Ahrar's call as owner of the dbt project.
3. **Lane 4:** confirm the verdict card fields above are sufficient, and whether `dial_explanation` should carry the breadth fraction as text ("7 of 11") or the dashboard formats it.
