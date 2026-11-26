# Phase 2 monitoring: definitions (#91)

Lane 3 writes the definitions; Lane 5 builds the plumbing (scheduled query or Airflow task, alert channel). Everything below runs weekly after the Friday scoring run, on the **served** model only (the `model_name` in `model_scores`). Thresholds are fixed now, before any live result, and changed only by a logged decision.

## 1. Accuracy and calibration on predictions whose outcome is known

A prediction's outcome is known 60 trading days (about 12 weeks) after its `as_of`, when `weekly_labels.label_status` turns `final`. So these numbers always trail by about 12 weeks; that is expected, not a bug.

- **Window:** the latest 26 `as_of` weeks with final labels, universe rows only (`role = 'universe'`).
- **Rolling AUC** of `prob_drop_20pct_60d` against `label_drop_20pct_60d`, and the same for the best baseline (from `model_predictions`).
- **Calibration:** rows split into five equal groups by predicted probability; per group, mean predicted vs observed rate. **Calibration gap** = the largest absolute difference across the five groups.
- **Base rate** in the window, next to the mean predicted probability.

| Status | Rule |
|---|---|
| alert | rolling AUC < 0.55, or below the best baseline's rolling AUC for 4 weeks in a row |
| watch | calibration gap > 0.10, or mean predicted differs from the base rate by more than 0.10 |
| ok | otherwise |

## 2. Feature drift (weekly)

Compared against the **training rows** (R4 train split, universe, model-eligible).

- **Stock-level features** (drawdown_252, ret_20d, ret_60d, ret_120d, vol_60d, volume_ratio_60d, beta_spx_120d, beta_arkk_120d, days_listed_capped): population stability index (PSI) of this week's model-eligible universe rows against training deciles of the same feature. PSI = sum over the 10 bins of (this_week_share - train_share) x ln(this_week_share / train_share), with shares floored at 0.001.
- **Market-level features** (spx_distance, credit_distance, universe_breadth): one value per week, so PSI does not apply. Flag the week when the value lies outside the 1st to 99th percentile of its training values.

| Status | Rule |
|---|---|
| alert | any stock-level PSI > 0.25, or any market-level feature outside its training 1st to 99th percentile |
| watch | any stock-level PSI between 0.10 and 0.25 |
| ok | otherwise |

A drift alert means "the model is being asked about conditions it did not see in training". It is reported next to the scores, not used to block them.

## 3. Data freshness and completeness

| Check | Alert when |
|---|---|
| Latest `raw.prices_raw.trade_date` | more than 1 trading day behind the last close (per `int_trading_calendar`) |
| Latest `model_scores.as_of` | not the most recent Friday trading day by Saturday 12:00 ET |
| `model_scores` rows for the latest week | differ from the count of model-eligible rows (universe + our basket) in `weekly_features` that week |
| Our 11 missing from `model_scores` | any active speculative name without a score, other than names under 126 trading days (e.g. SPCX until mid-December 2026) |

## 4. API health (Cloud Run `model-api`)

| Check | Alert when |
|---|---|
| 5xx share of requests | above 1% over the past 24 hours |
| p95 latency | above 2 seconds over the past 24 hours |
| `/health` | `as_of` differs from `max(as_of)` in `marts.model_scores`, or `data_source` is not `bigquery` once real scores exist |

Source: Cloud Run request logs / Cloud Monitoring metrics for the service.

## Suggested output table

`marts.model_monitoring`, one row per run x check: `run_date`, `check_group` (accuracy, calibration, drift, freshness, api), `check_name`, `model_name`, `model_version`, `value`, `threshold`, `status` (ok, watch, alert), `window_start`, `window_end`, `n_rows`, `computed_at`. The dashboard shows the latest status per check; Lane 5 routes `alert` rows to the team channel.
