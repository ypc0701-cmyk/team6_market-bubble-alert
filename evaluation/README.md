# Phase 2 evaluation (Lane 3)

Run in this order. Rules: decision log R3, R6 and R7; tables: schema contract v0.3.

## 1. Base-rate check, before any model is trained (R3, #81)

Paste `base_rate_check.sql` into the BigQuery console (or `bq query --use_legacy_sql=false < evaluation/base_rate_check.sql`) once `weekly_features` and `weekly_labels` exist. It reports the share of positive labels on training rows, overall and by year, and the R3 verdict:

- 10% to 40%: the 20% / 60-day label stands.
- Above 40%: the threshold moves to 25%. Below 10%: to 15%. Rerun once on the new threshold.

Log the result in `docs/decision_log.md` either way, **before** training. No other label change is allowed after results are seen.

## 2. Evaluation, after `model_predictions` exists (R6, R7, #82, #83, #84)

```
pip install pandas numpy db-dtypes google-cloud-bigquery
python evaluation/evaluate_phase2.py --bq-project market-bubble-alert --bq-dataset marts
python evaluation/evaluate_phase2.py --bq-project market-bubble-alert --bq-dataset marts --write-bq   # also loads marts.model_evaluation
```

Outputs go to `evaluation/output/`: `model_evaluation.csv` (contract columns), `calibration.csv`, `r7_by_year.csv`, `r7_hindsight.csv`, `our11_ranks.csv` and `report.md`, which states in plain words whether the ML model beats the simple rules.

How the call is made (R6, fixed before any result): the candidate is the better of `logistic` and `boosted_trees` on validation AUC, and the best baseline is the better of `baseline_drawdown` and `baseline_vol` on validation AUC. The test period is read once: the candidate is served only if the 90% block-bootstrap interval of its AUC minus the best baseline's AUC, on the same resampled weeks, lies above zero. Blocks of 13 weeks, 1,000 resamples, seed 882.

Offline check: `python evaluation/evaluate_phase2.py --csv-dir docs/dummy_rows/phase2` runs on the contract dummy rows (one labeled week, so intervals collapse; it only proves the plumbing).
