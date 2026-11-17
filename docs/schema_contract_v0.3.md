# Schema contract v0.3: Phase 2 addendum (draft for comment)

BA882 · Market Bubble Early Warning System · Lane 3 · circulated Monday Nov 16, 2026 · comments from Lanes 1, 2, 4 and 5 by end of day Tuesday Nov 17 · frozen Wednesday Nov 18.

This addendum covers the Phase 2 tables only. The Phase 1 tables in [schema_contract.md](schema_contract.md) (v0.2) are unchanged, and every Phase 1 convention still applies unless section 1 below amends it. The rules behind these columns are in the decision log under "Phase 2 rules (Lane 3)"; a tag such as [R2] points to rule 2 there. As in Phase 1, the dbt YAML is what the build enforces and this page is what people read. If they disagree, fix both in the same pull request.

The agreed design is in [phase2_proposal.md](phase2_proposal.md) (PR #68). Where this contract differs from the proposal, section 5 lists the difference and the reason.

## 1. Conventions: what changes from v0.2

1. **Tracked symbols (amends C9).** A tracked symbol is any ticker in `basket_members` or `universe_members`. The extractor loads the union. The `relationships` test on `raw.prices_raw.ticker` must accept the union, and that change merges before the first universe load, otherwise `dbt build` fails and `daily_signals` stops updating (Lane 1, issue #79).
2. **The official dial is isolated from the universe.** The partial-load hold-back in `int_trading_calendar` keeps reading `basket_members` only, so a missing universe ticker never delays the official dial.
3. **Phase 1 marts do not move.** The backfill to January 2020 adds older rows for `^GSPC`, ARKK, HYG, IEF, SPY, RSP and for basket tickers that also sit in the universe. `int_trading_calendar` takes `cal_start` from the first day in the warehouse, so without a guard the Phase 1 marts would grow history before 2024-10-01 and `days_listed` would change. The Phase 1 calendar is floored at 2024-10-01. Acceptance: `daily_signals`, `daily_drawdowns`, `credit_daily` and `episodes` are row-for-row identical before and after the backfill.
4. **Weekly grain.** Phase 2 feature, label and score tables have one row per ticker per week. The week's date column is `as_of` (DATE): the last trading day of the calendar week, which is Friday unless Friday is a market holiday. `as_of` matches the field the model API already serves.
5. **Windows** are trading days on the `^GSPC` calendar, end at `as_of` inclusive, and read adjusted close, as in v0.2 (C5, C6). Nothing is forward-filled.
6. **No look-ahead.** A feature on `as_of` reads prices dated on or before `as_of`. A label on `as_of` reads prices dated strictly after `as_of`. Each has a dbt test.
7. **Role.** Every Phase 2 row carries `role`: `universe` (a rule-selected AI stock, usable for training) or `our_basket` (one of our 11 speculative names, never used for training, scored out of sample) [R2].

## 2. The tables

### universe_members (dbt seed, owner Lane 2, content owner Lane 3)

One row per (ticker, added_date), a type 2 slowly changing dimension modeled on `basket_members`. The list is produced by rule from the ETF holdings snapshot [R1]; nobody adds a ticker by hand.

| Column | Type | Null | Meaning | Trace |
|---|---|---|---|---|
| ticker | STRING | no | Uppercase yfinance symbol | C1 |
| company_name | STRING | no | Display name | L4 |
| source_etfs | STRING | no | ETFs holding the name on the snapshot date, pipe-separated and sorted, e.g. `AIQ\|ARTY` | R1 |
| n_source_etfs | INT64 | no | Count of those ETFs | R1 |
| listing_date | DATE | no | Yahoo's first available date, as in Phase 1 | C §3 |
| snapshot_date | DATE | no | Date of the holdings files this row came from | R1 |
| added_date | DATE | no | First date the span is in force. 2020-01-01 for the founding snapshot, so the backfill is covered | R1 |
| removed_date | DATE | yes | First date no longer in force; NULL = current | R1 |
| added_reason | STRING | no | `etf_snapshot` | R1 |
| removed_reason | STRING | yes | `delisting_or_acquisition`, `dropped_at_refresh` | R1 |
| notes | STRING | yes | | |

Tests: unique (ticker, added_date); no overlapping spans per ticker; **no ticker that has a speculative span in `basket_members`** [R2]; reasons in list. Megacap names (NVDA, MSFT and so on) may appear here when an ETF holds them; they are ordinary universe members.

### weekly_features (mart, one row per as_of × ticker, owner Lane 2)

Rows exist for every universe member and every speculative basket member once the ticker has 60 trading days of history. The first usable `as_of` is in January 2021, because the longest window needs 252 trading days of the backfill.

| Column | Type | Null | Meaning | Trace |
|---|---|---|---|---|
| as_of | DATE | no | Last trading day of the week | C4 above |
| ticker | STRING | no | | |
| role | STRING | no | `universe` or `our_basket` | R2 |
| adj_close | FLOAT64 | no | Adjusted close on as_of | C5 |
| days_listed | INT64 | no | Trading days since `listing_date`, inclusive | v0.2 |
| adv_20d_usd | FLOAT64 | yes | Mean of close × volume over the trailing 20 days | R1 |
| drawdown_252 | FLOAT64 | yes | adj_close / max adj_close over the trailing 252 days (or the days available) - 1. Baseline A | R5 |
| ret_20d, ret_60d, ret_120d | FLOAT64 | yes | adj_close / adj_close N trading days earlier - 1 | R5 |
| vol_60d | FLOAT64 | yes | Sample standard deviation of the trailing 60 daily log returns × sqrt(252). Baseline B | R5 |
| volume_ratio_60d | FLOAT64 | yes | Mean volume over the trailing 5 days / mean volume over the trailing 60 days | R5 |
| beta_spx_120d, beta_arkk_120d | FLOAT64 | yes | Covariance of the stock's daily returns with the reference's / variance of the reference's, trailing 120 returns | R5 |
| days_listed_capped | INT64 | no | least(days_listed, 1260), so "listed long ago" reads the same for every old name | R5 |
| spx_distance | FLOAT64 | no | ^GSPC adj_close / trailing 252-day high - 1; same value for every ticker that week | R5 |
| credit_distance | FLOAT64 | no | HYG/IEF ratio / trailing 126-day high - 1 | R5 |
| universe_breadth | FLOAT64 | yes | Share of model-eligible `universe` rows that week with drawdown_252 <= -0.25. Our 11 are not in it | R2, R5 |
| is_model_eligible | BOOL | no | days_listed >= 126 AND unadjusted close > 2 AND adv_20d_usd >= 5,000,000 AND every feature above is non-NULL | R1, R5 |
| computed_at | TIMESTAMP | no | | |

The twelve model inputs are: drawdown_252, ret_20d, ret_60d, ret_120d, vol_60d, volume_ratio_60d, beta_spx_120d, beta_arkk_120d, days_listed_capped, spx_distance, credit_distance, universe_breadth. Nothing else is a feature. The official dial level is **not** a feature [R5].

Tests: unique (as_of, ticker); drawdown_252 in [-1, 0]; universe_breadth in [0, 1]; role in list; one singular test that no row reads a price after its as_of (demonstrated by seeding a future-dated row and watching it fail).

### weekly_labels (mart, one row per as_of × ticker, owner Lane 2)

Same keys as `weekly_features`.

| Column | Type | Null | Meaning | Trace |
|---|---|---|---|---|
| as_of, ticker, role | | no | | |
| fwd_days_available | INT64 | no | Trading days after as_of present on the calendar, capped at 60 | R3 |
| fwd_min_adj_close | FLOAT64 | yes | Lowest adj_close of the ticker over trading days as_of+1 through as_of+60 | R3 |
| fwd_min_return | FLOAT64 | yes | fwd_min_adj_close / adj_close on as_of - 1 | R3 |
| label_drop_20pct_60d | INT64 | yes | 1 if fwd_min_return <= -0.20, else 0. NULL while label_status is `pending` | R3 |
| label_status | STRING | no | `final` (60 forward days exist), `pending` (fewer than 60 exist yet), `truncated` (the ticker stopped trading inside the window; labeled from the days it has) | R3 |
| split | STRING | no | `train`, `validation`, `test`, `gap` or `unlabeled`, from the dates in R4 | R4 |
| computed_at | TIMESTAMP | no | | |

Split dates, fixed before any training [R4]:

| split | as_of from | as_of through |
|---|---|---|
| train | 2021-01-08 | 2024-06-28 |
| gap | 2024-07-05 | 2024-09-27 |
| validation | 2024-10-04 | 2025-06-27 |
| gap | 2025-07-04 | 2025-09-26 |
| test | 2025-10-03 | last as_of with label_status `final` |
| unlabeled | every later as_of | |

Tests: unique key; label in {0, 1} or NULL; label NULL exactly when status is `pending`; split in list; the leakage test (no label reads a price on or before its own as_of).

A training row is: role = `universe` AND is_model_eligible AND split = `train` AND label not NULL. Validation and test rows use the same filter with their split.

### model_predictions (mart, one row per as_of × ticker × model_name, owner Lane 2, read by Lane 3)

Every model's probability for every model-eligible row, labeled or not. This is what the evaluation reads.

| Column | Type | Null | Meaning |
|---|---|---|---|
| as_of, ticker, role | | no | |
| model_name | STRING | no | `baseline_drawdown`, `baseline_vol`, `logistic`, `boosted_trees` |
| model_version | STRING | no | Version registered in MLflow for the run that produced the row |
| prob_drop_20pct_60d | FLOAT64 | no | Predicted probability, 0 to 1 |
| split | STRING | no | Copied from weekly_labels |
| scored_at | TIMESTAMP | no | |

### model_scores (mart, one row per as_of × ticker, owner Lane 2, read by Lanes 4 and 5)

The served model only, so the API's "latest as_of" query returns one row per ticker. The first five columns are exactly the ones the API in PR #98 expects.

| Column | Type | Null | Meaning |
|---|---|---|---|
| ticker | STRING | no | |
| as_of | DATE | no | |
| prob_drop_20pct_60d | FLOAT64 | no | From the served model |
| rank_in_universe | INT64 | no | 1 = highest probability among `universe` rows that week. For an `our_basket` row: 1 + the number of universe rows with a higher probability, which is where the name would sit in the universe |
| model_version | STRING | no | |
| model_name | STRING | no | Which of the four models is served [R6] |
| role | STRING | no | `universe` or `our_basket`; the API and dashboard read the basket from here instead of a hard-coded list |
| universe_size | INT64 | no | Count of `universe` rows scored that week |
| pct_rank_in_universe | FLOAT64 | no | rank_in_universe / universe_size, capped at 1 |
| prob_change_1w | FLOAT64 | yes | Change from the previous as_of; NULL on a ticker's first scored week |
| scored_at | TIMESTAMP | no | |

Tests: unique (as_of, ticker); probability in [0, 1]; exactly one model_name per as_of.

A basket name with fewer than 126 trading days of history has no row. Today that is SPCX (listed 2026-06-12), which becomes scorable in mid-December 2026. The API already reports such names under `missing_from_scores`.

### model_evaluation (mart, one row per model_name × split × metric, owner Lane 3)

What the dashboard's model card reads.

| Column | Type | Null | Meaning |
|---|---|---|---|
| model_name, model_version | STRING | no | |
| split | STRING | no | `validation` or `test` |
| population | STRING | no | `universe` or `our_basket` |
| metric | STRING | no | `auc`, `precision_top_decile`, `brier`, `base_rate`, `mean_predicted` |
| value | FLOAT64 | no | |
| ci_low, ci_high | FLOAT64 | yes | 90% interval from a block bootstrap over weeks, blocks of 13 weeks, 1,000 resamples [R6]. NULL for base_rate |
| n_rows, n_weeks | INT64 | no | |
| beats_best_baseline | BOOL | yes | Set on `auc` rows of the two models: TRUE when the bootstrap interval of (model AUC - best baseline AUC) lies above zero [R6] |
| evaluated_at | TIMESTAMP | no | |

### universe_dial_daily (mart, one row per trade_date, owner Lane 3)

The Phase 1 dial logic with the speculative leg computed on the universe instead of our 11. Megacap, S&P, concentration and credit legs are read from `daily_signals` unchanged. Built Nov 21; columns fixed now so Lane 4 can lay out the robustness panel.

| Column | Type | Null | Meaning |
|---|---|---|---|
| trade_date | DATE | no | From 2024-10-01, the same span as `daily_signals` |
| univ_members_valid | INT64 | no | Universe names with a span in force, 60+ days listed and a drawdown that day |
| univ_members_broken | INT64 | no | Of those, drawdown <= -0.25 |
| universe_breadth | FLOAT64 | yes | broken / valid |
| universe_median_drawdown | FLOAT64 | yes | |
| cond_divergence | BOOL | no | Same thresholds as Phase 1: breadth >= 0.50 AND median <= -0.15 AND spx_distance > -0.05 |
| is_armed | BOOL | no | Same memory rules as Phase 1 |
| armed_since | DATE | yes | |
| universe_dial_level | INT64 | no | 0 to 5, same top-down rule |
| universe_dial_label | STRING | no | |
| official_dial_level | INT64 | no | Copied from `daily_signals` for the one-SELECT comparison |
| dials_agree | BOOL | no | universe_dial_level = official_dial_level |
| computed_at | TIMESTAMP | no | |

## 3. Hard cases the contract was checked against

**Our 11 inside the ETFs.** Several of our speculative names are held by AI ETFs. The seed test on `universe_members` makes it impossible to seed one, `role` keeps them out of every training filter, and `universe_breadth` is computed on `universe` rows only, so our basket cannot reach the model through a market feature either.

**Hindsight in the filters.** Price and liquidity are checked twice: once at the snapshot to select the list, and again on every `as_of` through `is_model_eligible`. A name that qualifies today but traded $1M a day in 2021 does not contribute 2021 rows.

**Overlapping labels.** Consecutive weekly rows of one stock share most of their 60-day window. The gaps between splits remove overlap across splits; inside a split it remains, which is why the evaluation's intervals come from a block bootstrap over weeks and why `n_weeks` sits next to `n_rows`.

**Stocks that stop trading.** A window cut short by a delisting or acquisition is labeled from the days that exist and marked `truncated`. With a universe taken from today's holdings these are rare; the survivorship this hides is a known limit [R7].

**The dial on a bigger basket.** `universe_dial_daily` starts on 2024-10-01 like the official dial, so the two are compared over the same days with the same memory rules. Universe members need only a span in force and 60 days listed, as in Phase 1.

## 4. Dummy rows

`docs/dummy_rows/phase2/` holds a small consistent set for every table above, written by `docs/dummy_rows/make_phase2_dummy_rows.py`. The tickers are our 11 plus nine well-known AI names used as placeholders. **They are not the selected universe**; the list is drawn only after the rules are merged [R1]. Every number is made up and `model_version` is `dummy-0`.

## 5. Differences from the proposal, and open items for the freeze

1. **Official dial level dropped as a feature.** It exists only from late 2024 and is built from our 11, so it cannot cover 2021 to 2024 training rows and it would route our basket into the model. `universe_breadth` carries the "how broad is the selling" information [R5].
2. **Eligibility checked on every date**, in addition to the snapshot filter in the proposal [R1].
3. **126 trading days of history to be scored**, against 60 in the proposal, because ret_120d and the 120-day betas need it. 60 days is still the bar to get a row.
4. **Two extra tables**, `model_predictions` and `model_evaluation`, so `model_scores` can hold exactly one row per ticker per week for the API.
5. **Lane 2 and Lane 5:** training engine. Proposed: BigQuery ML (`LOGISTIC_REG` and `BOOSTED_TREE_CLASSIFIER`), with a short Python step in the weekly Airflow task that logs parameters and metrics to MLflow. Needs Ahrar's and Chloe's agreement (#94).
6. **Lane 2:** how the union of tracked tickers is implemented (a model over both seeds, or two tests), and which dataset holds the BigQuery ML model objects.
7. **Lane 1:** confirm the backfill includes `^GSPC`, ARKK, HYG and IEF back to January 2020; the betas, spx_distance and credit_distance need them.
8. **Lane 5:** the API can drop its hard-coded basket list and its own `universe_size` and median once it reads `role`, `universe_size` and `pct_rank_in_universe`.
9. **Lane 4:** confirm these columns cover the risk panel, the robustness panel and the model card.
