"""Phase 2 evaluation (Lane 3): models versus baselines, our 11, known limits.

Implements decision log R6 and R7 and fills the `model_evaluation` mart of schema contract v0.3.
Issues #81 (baselines on the test period), #82 (evaluation report), #83 (our 11 out of sample)
and #84 (known limits measured).

Reads (contract v0.3):
  model_predictions  as_of, ticker, role, model_name, model_version, trained_at,
                     prob_drop_20pct_60d, split, scored_at
  weekly_labels      as_of, ticker, role, label_drop_20pct_60d, label_status, split
  universe_members   ticker, listing_date (for the R7 hindsight check)

Writes to --out (default evaluation/output/):
  model_evaluation.csv   contract columns, one row per model x split x population x metric
  calibration.csv        test-period calibration table, deciles of predicted probability
  r7_by_year.csv         base rate and AUC by calendar year, per model (R7 item 1)
  r7_hindsight.csv       test-period AUC on names with 5+ years of history in Jan 2021 (R7 item 2)
  our11_ranks.csv        our 11's percentile ranks in the universe, per week (R7 item 3, #83)
  report.md              plain-language summary, including whether ML beats the simple rules

Sources:
  --csv-dir DIR                      CSVs named after the tables (e.g. docs/dummy_rows/phase2)
  --bq-project P --bq-dataset D      read the marts from BigQuery
  --write-bq                         also load model_evaluation into BigQuery (WRITE_TRUNCATE)

R6, fixed before any result: AUC, precision in the top 10% of scores, Brier score and a
calibration table on validation and test, each next to the base rate. 90% intervals from a
moving block bootstrap that resamples whole weeks in blocks of 13, 1,000 times, seeded. The ML
candidate is the better of logistic and boosted_trees on validation AUC; the best baseline is the
better baseline on validation AUC, so the test period is used for nothing but the final reading.
"beats_best_baseline" is TRUE when the 90% interval of (model AUC - best baseline AUC), computed
on the same resampled weeks, lies above zero.
"""
import argparse
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

BASELINES = ["baseline_drawdown", "baseline_vol"]
ML_MODELS = ["logistic", "boosted_trees"]
SPLITS = ["validation", "test"]
POPULATIONS = ["universe", "our_basket"]
BLOCK_WEEKS = 13
N_BOOT = 1000
CI = 0.90
SEED = 882
HISTORY_CUTOFF = pd.Timestamp("2016-01-08")  # 5 years before the first training week (R7 item 2)


# ---------------------------------------------------------------- metrics

def auc(y, p):
    """Area under the ROC curve via the rank-sum identity; ties get average ranks. NaN if one class."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    n1 = y.sum()
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    ranks = pd.Series(p).rank(method="average").to_numpy()
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def precision_top_decile(y, p):
    """Share of positives among the top 10% of scores (at least one row)."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    if len(y) == 0:
        return np.nan
    k = max(1, int(np.ceil(0.10 * len(y))))
    top = np.argsort(-p, kind="mergesort")[:k]
    return y[top].mean()


def brier(y, p):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    return np.mean((p - y) ** 2) if len(y) else np.nan


METRICS = {
    "auc": auc,
    "precision_top_decile": precision_top_decile,
    "brier": brier,
    "base_rate": lambda y, p: np.mean(y) if len(y) else np.nan,
    "mean_predicted": lambda y, p: np.mean(p) if len(p) else np.nan,
}


# ---------------------------------------------------------------- bootstrap

def block_resamples(weeks, rng, n_boot=N_BOOT, block=BLOCK_WEEKS):
    """Moving block bootstrap over an ordered list of weeks. Returns n_boot arrays of week positions."""
    n = len(weeks)
    if n == 0:
        return []
    b = min(block, n)
    starts = np.arange(n - b + 1)
    n_blocks = int(np.ceil(n / b))
    out = []
    for _ in range(n_boot):
        s = rng.choice(starts, size=n_blocks, replace=True)
        idx = np.concatenate([np.arange(x, x + b) for x in s])[:n]
        out.append(idx)
    return out


def rows_for(week_idx, week_rows):
    """Row positions for a resample of weeks (a week drawn twice contributes its rows twice)."""
    return np.concatenate([week_rows[i] for i in week_idx]) if len(week_idx) else np.array([], int)


def interval(values):
    v = np.asarray([x for x in values if not np.isnan(x)])
    if len(v) == 0:
        return np.nan, np.nan
    lo, hi = np.quantile(v, [(1 - CI) / 2, 1 - (1 - CI) / 2])
    return float(lo), float(hi)


# ---------------------------------------------------------------- data

def load(args):
    if args.csv_dir:
        d = Path(args.csv_dir)
        preds = pd.read_csv(d / "model_predictions.csv")
        labels = pd.read_csv(d / "weekly_labels.csv")
        members = pd.read_csv(d / "universe_members.csv") if (d / "universe_members.csv").exists() else None
    else:
        from google.cloud import bigquery
        client = bigquery.Client(project=args.bq_project)
        ds = f"{args.bq_project}.{args.bq_dataset}"
        preds = client.query(f"select * from `{ds}.model_predictions`").to_dataframe()
        labels = client.query(
            f"select as_of, ticker, role, label_drop_20pct_60d, label_status, split "
            f"from `{ds}.weekly_labels`").to_dataframe()
        members = client.query(
            f"select ticker, min(listing_date) as listing_date from `{ds}.universe_members` group by ticker"
        ).to_dataframe()
    for df in (preds, labels):
        df["as_of"] = pd.to_datetime(df["as_of"])
    # The label and its split come from weekly_labels; predictions carry a copy of split that must agree.
    df = preds.merge(
        labels[["as_of", "ticker", "label_drop_20pct_60d", "label_status", "split"]],
        on=["as_of", "ticker"], how="left", suffixes=("", "_label"))
    mismatch = df[df["split_label"].notna() & (df["split"] != df["split_label"])]
    if len(mismatch):
        raise SystemExit(f"{len(mismatch)} prediction rows disagree with weekly_labels on split; fix upstream first")
    df = df[df["label_drop_20pct_60d"].notna()].copy()
    df["y"] = df["label_drop_20pct_60d"].astype(int)
    if members is not None:
        members["listing_date"] = pd.to_datetime(members["listing_date"])
    return preds, df, members


# ---------------------------------------------------------------- evaluation

def evaluate(df, rng):
    """model_evaluation rows plus the paired-difference results used for beats_best_baseline."""
    rows = []
    boot_auc = {}  # (model, split, population) -> array of resampled AUCs aligned across models
    for split in SPLITS:
        for pop in POPULATIONS:
            sub = df[(df["split"] == split) & (df["role"] == pop)]
            if sub.empty:
                continue
            weeks = np.sort(sub["as_of"].unique())
            resamples = block_resamples(weeks, rng, n_boot=N_BOOT)
            for model, g in sub.groupby("model_name"):
                g = g.reset_index(drop=True)
                pos = {w: i for i, w in enumerate(weeks)}
                week_rows = [[] for _ in weeks]
                for r, w in enumerate(g["as_of"].to_numpy()):
                    week_rows[pos[w]].append(r)
                week_rows = [np.array(x, int) for x in week_rows]
                y, p = g["y"].to_numpy(), g["prob_drop_20pct_60d"].to_numpy(dtype=float)
                boots = {m: [] for m in METRICS}
                for idx in resamples:
                    r = rows_for(idx, week_rows)
                    for m, f in METRICS.items():
                        boots[m].append(f(y[r], p[r]))
                boot_auc[(model, split, pop)] = np.asarray(boots["auc"], dtype=float)
                for m, f in METRICS.items():
                    lo, hi = (np.nan, np.nan) if m == "base_rate" else interval(boots[m])
                    rows.append({
                        "model_name": model,
                        "model_version": g["model_version"].iloc[0],
                        "trained_at": g["trained_at"].iloc[0],
                        "split": split, "population": pop, "metric": m,
                        "value": f(y, p), "ci_low": lo, "ci_high": hi,
                        "n_rows": len(g), "n_weeks": g["as_of"].nunique(),
                        "beats_best_baseline": None,
                    })
    ev = pd.DataFrame(rows)
    return ev, boot_auc


def pick(ev, names):
    """Best of `names` on validation AUC, universe population; None if none present."""
    v = ev[(ev["split"] == "validation") & (ev["population"] == "universe")
           & (ev["metric"] == "auc") & ev["model_name"].isin(names)]
    v = v.dropna(subset=["value"])
    return None if v.empty else v.sort_values("value", ascending=False)["model_name"].iloc[0]


def set_beats(ev, boot_auc):
    best_base = pick(ev, BASELINES)
    decisions = {}
    if best_base is None:
        return ev, best_base, decisions
    for model in ML_MODELS:
        for split in SPLITS:
            for pop in POPULATIONS:
                a, b = boot_auc.get((model, split, pop)), boot_auc.get((best_base, split, pop))
                if a is None or b is None:
                    continue
                lo, hi = interval(a - b)
                beats = bool(lo > 0) if not np.isnan(lo) else None
                mask = ((ev["model_name"] == model) & (ev["split"] == split)
                        & (ev["population"] == pop) & (ev["metric"] == "auc"))
                ev.loc[mask, "beats_best_baseline"] = beats
                decisions[(model, split, pop)] = (lo, hi, beats)
    return ev, best_base, decisions


def calibration(df):
    t = df[(df["split"] == "test") & (df["role"] == "universe")].copy()
    if t.empty:
        return pd.DataFrame()
    t["decile"] = t.groupby("model_name")["prob_drop_20pct_60d"].transform(
        lambda s: pd.qcut(s.rank(method="first"), q=min(10, len(s)), labels=False) + 1)
    return (t.groupby(["model_name", "decile"])
             .agg(n_rows=("y", "size"), mean_predicted=("prob_drop_20pct_60d", "mean"),
                  observed_rate=("y", "mean"))
             .reset_index())


def r7_by_year(df):
    """R7 item 1: regime dependence. Training years are in-sample and marked as such."""
    d = df[df["role"] == "universe"].copy()
    d["year"] = d["as_of"].dt.year
    out = []
    for (model, year), g in d.groupby(["model_name", "year"]):
        out.append({"model_name": model, "year": year,
                    "splits": "|".join(sorted(g["split"].unique())),
                    "in_sample": bool((g["split"] == "train").any()),
                    "n_rows": len(g), "base_rate": g["y"].mean(),
                    "auc": auc(g["y"], g["prob_drop_20pct_60d"])})
    res = pd.DataFrame(out)
    train = d[(d["split"] == "train")].drop_duplicates(["as_of", "ticker"])
    share_2022 = (train.loc[train["y"] == 1, "as_of"].dt.year == 2022).mean() if (train["y"] == 1).any() else np.nan
    return res, share_2022


def r7_hindsight(df, members):
    """R7 item 2: test-period AUC on names that already had 5+ years of history in January 2021."""
    if members is None:
        return pd.DataFrame()
    old = set(members.loc[members["listing_date"] <= HISTORY_CUTOFF, "ticker"])
    t = df[(df["split"] == "test") & (df["role"] == "universe")]
    out = []
    for model, g in t.groupby("model_name"):
        s = g[g["ticker"].isin(old)]
        out.append({"model_name": model, "auc_all": auc(g["y"], g["prob_drop_20pct_60d"]),
                    "n_all": len(g), "auc_5y_history": auc(s["y"], s["prob_drop_20pct_60d"]),
                    "n_5y_history": len(s), "tickers_5y_history": s["ticker"].nunique()})
    return pd.DataFrame(out)


def our11_ranks(preds, served):
    """R7 item 3 and #83: each week, where each of our 11 sits in the universe's distribution.
    Uses every scored week (labeled or not), so it is out of sample for the test period onward."""
    p = preds[preds["model_name"] == served].copy()
    if p.empty:
        return pd.DataFrame(), {}
    out = []
    for w, g in p.groupby("as_of"):
        uni = np.sort(g.loc[g["role"] == "universe", "prob_drop_20pct_60d"].to_numpy(dtype=float))
        if len(uni) == 0:
            continue
        med = float(np.median(uni))
        for _, r in g[g["role"] == "our_basket"].iterrows():
            share_below = np.searchsorted(uni, r["prob_drop_20pct_60d"], side="left") / len(uni)
            out.append({"as_of": w.date(), "ticker": r["ticker"], "split": r["split"],
                        "prob": r["prob_drop_20pct_60d"], "universe_median_prob": med,
                        "universe_percentile": share_below})
    res = pd.DataFrame(out)
    if res.empty:
        return res, {}
    latest = res[res["as_of"] == res["as_of"].max()]
    summary = {
        "latest_week": str(res["as_of"].max()),
        "latest_median_percentile_of_our_11": float(latest["universe_percentile"].median()),
        "latest_share_of_our_11_above_universe_median": float((latest["universe_percentile"] > 0.5).mean()),
        "test_period_median_percentile": float(res.loc[res["split"] == "test", "universe_percentile"].median())
        if (res["split"] == "test").any() else np.nan,
    }
    return res, summary


# ---------------------------------------------------------------- report

def fmt(x, pct=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x:.1%}" if pct else f"{x:.3f}"


def report(ev, best_base, decisions, by_year, share_2022, hindsight, our11_summary, served):
    cand = pick(ev, ML_MODELS)
    L = ["# Phase 2 evaluation", "",
         f"Evaluated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC. Rules: decision log R6 and R7.", ""]
    test_u = ev[(ev["split"] == "test") & (ev["population"] == "universe")]
    if not test_u.empty:
        L += ["## Test period, universe", "",
              "| Model | AUC (90% CI) | Top-decile precision | Brier | Base rate | Rows | Weeks |",
              "|---|---|---|---|---|---|---|"]
        for model in BASELINES + ML_MODELS:
            g = test_u[test_u["model_name"] == model].set_index("metric")
            if g.empty:
                continue
            a = g.loc["auc"]
            L.append(f"| {model} | {fmt(a['value'])} ({fmt(a['ci_low'])} to {fmt(a['ci_high'])}) "
                     f"| {fmt(g.loc['precision_top_decile','value'], True)} | {fmt(g.loc['brier','value'])} "
                     f"| {fmt(g.loc['base_rate','value'], True)} | {int(a['n_rows'])} | {int(a['n_weeks'])} |")
        L.append("")
    L += ["## Does the ML beat the simple rules?", ""]
    if cand and best_base and (cand, "test", "universe") in decisions:
        lo, hi, beats = decisions[(cand, "test", "universe")]
        verdict = ("Yes: the interval of the AUC difference lies above zero, so the ML model is served."
                   if beats else
                   "No: the interval of the AUC difference includes zero (or lies below it), so the "
                   "difference cannot be told apart from noise on this test period, and the best baseline is served.")
        L += [f"Candidate (best ML on validation AUC): **{cand}**. Best baseline (validation AUC): **{best_base}**.",
              f"Test-period AUC difference, 90% block-bootstrap interval: {fmt(lo)} to {fmt(hi)}.", "", verdict, ""]
    else:
        L += ["Not enough labeled rows to compare yet.", ""]
    L += ["## Known limits (R7)", ""]
    if not np.isnan(share_2022):
        L.append(f"- Share of training positives that fall in 2022: {fmt(share_2022, True)}. "
                 "The training period has one bear market; results lean on it.")
    if not hindsight.empty:
        h = hindsight[hindsight["model_name"] == (cand or served)]
        if not h.empty:
            h = h.iloc[0]
            L.append(f"- Hindsight universe: test AUC {fmt(h['auc_all'])} on all names vs "
                     f"{fmt(h['auc_5y_history'])} on the {int(h['tickers_5y_history'])} names with 5+ years "
                     "of history in January 2021, a group today's ETF fashion selected less.")
    L.append("- Survivorship (stated, not measured): names delisted or dropped from ETFs before the snapshot "
             "are absent, so past falls are understated and the base rate is biased down.")
    if not by_year.empty:
        L.append("- Base rate and AUC by calendar year are in r7_by_year.csv; training years are in-sample.")
    L.append("")
    if our11_summary:
        L += ["## Our 11 against the universe (#83)", "",
              f"Served model: {served}. Week of {our11_summary['latest_week']}: the median of our 11 sits at the "
              f"{fmt(our11_summary['latest_median_percentile_of_our_11'], True)} percentile of the universe's "
              f"predicted risk; {fmt(our11_summary['latest_share_of_our_11_above_universe_median'], True)} of them "
              f"are above the universe median. Test period median percentile: "
              f"{fmt(our11_summary['test_period_median_percentile'], True)}.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- main

def main():
    global N_BOOT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv-dir")
    ap.add_argument("--bq-project", default="market-bubble-alert")
    ap.add_argument("--bq-dataset", default="marts")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "output"))
    ap.add_argument("--write-bq", action="store_true")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    args = ap.parse_args()
    N_BOOT = args.n_boot

    rng = np.random.default_rng(SEED)
    preds, df, members = load(args)
    preds = preds.copy()
    preds["as_of"] = pd.to_datetime(preds["as_of"])

    ev, boot_auc = evaluate(df, rng)
    ev, best_base, decisions = set_beats(ev, boot_auc)
    cand = pick(ev, ML_MODELS)
    served = best_base
    if cand and (cand, "test", "universe") in decisions and decisions[(cand, "test", "universe")][2]:
        served = cand
    served = served or (preds["model_name"].iloc[0] if len(preds) else None)

    ev["evaluated_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    by_year, share_2022 = r7_by_year(df)
    hind = r7_hindsight(df, members)
    ranks, our11_summary = our11_ranks(preds, served)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cols = ["model_name", "model_version", "trained_at", "split", "population", "metric", "value",
            "ci_low", "ci_high", "n_rows", "n_weeks", "beats_best_baseline", "evaluated_at"]
    ev[cols].to_csv(out / "model_evaluation.csv", index=False, float_format="%.6f")
    calibration(df).to_csv(out / "calibration.csv", index=False, float_format="%.6f")
    by_year.to_csv(out / "r7_by_year.csv", index=False, float_format="%.6f")
    hind.to_csv(out / "r7_hindsight.csv", index=False, float_format="%.6f")
    ranks.to_csv(out / "our11_ranks.csv", index=False, float_format="%.6f")
    (out / "report.md").write_text(report(ev, best_base, decisions, by_year, share_2022, hind,
                                          our11_summary, served), encoding="utf-8")
    print(f"{len(ev)} model_evaluation rows; candidate={cand}; best baseline={best_base}; served={served}")
    print(f"outputs in {out}")

    if args.write_bq:
        from google.cloud import bigquery
        client = bigquery.Client(project=args.bq_project)
        table = f"{args.bq_project}.{args.bq_dataset}.model_evaluation"
        e = ev[cols].copy()
        e["trained_at"] = pd.to_datetime(e["trained_at"], utc=True)
        e["evaluated_at"] = pd.to_datetime(e["evaluated_at"], utc=True)
        e["beats_best_baseline"] = e["beats_best_baseline"].astype("boolean")
        job = client.load_table_from_dataframe(
            e, table, job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"))
        job.result()
        print(f"loaded {len(e)} rows into {table}")


if __name__ == "__main__":
    main()
