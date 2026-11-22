"""Generate internally consistent dummy rows for every schema contract v0.3 table.

Scenario: three weekly dates. 2026-08-14 has final labels (test split); 2026-11-06 and 2026-11-13
are still pending, so they are scored only. The tickers are our 11 plus nine well-known AI names
used as PLACEHOLDERS. They are not the selected universe: that list is drawn by rule only after the
Phase 2 rules are merged (decision log R1). Every number is made up; model_version is dummy-0.

Run from the repo root:  python docs/dummy_rows/make_phase2_dummy_rows.py
"""
import csv
import pathlib
import random
import statistics
from datetime import date, datetime, timezone

random.seed(882)
OUT = pathlib.Path(__file__).parent / "phase2"
OUT.mkdir(exist_ok=True)
NOW = datetime(2026, 11, 14, 2, 0, tzinfo=timezone.utc).isoformat()
TRAINED = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc).isoformat()  # trained_at of dummy-0
SNAPSHOT = date(2026, 11, 17)
AS_OF = [date(2026, 8, 14), date(2026, 11, 6), date(2026, 11, 13)]
SPLIT = {AS_OF[0]: "test", AS_OF[1]: "unlabeled", AS_OF[2]: "unlabeled"}
MODELS = ["baseline_drawdown", "baseline_vol", "logistic", "boosted_trees"]
SERVED = "logistic"

# ticker: (name, role, listing_date, price, drawdown, vol, source_etfs)
T = {
    "CRWV": ("CoreWeave", "our_basket", "2025-03-28", 108.0, -0.42, 0.95, ""),
    "NBIS": ("Nebius", "our_basket", "2024-10-21", 129.0, -0.09, 0.80, ""),
    "IREN": ("IREN", "our_basket", "2021-11-17", 26.0, -0.31, 0.90, ""),
    "APLD": ("Applied Digital", "our_basket", "2020-01-02", 16.4, -0.27, 0.88, ""),
    "WULF": ("TeraWulf", "our_basket", "2020-01-02", 7.9, -0.36, 0.92, ""),
    "CIFR": ("Cipher Mining", "our_basket", "2020-10-20", 6.9, -0.29, 0.90, ""),
    "SMCI": ("Super Micro", "our_basket", "2020-01-02", 44.0, -0.33, 0.75, ""),
    "AI": ("C3.ai", "our_basket", "2020-12-09", 17.4, -0.44, 0.70, ""),
    "SOUN": ("SoundHound", "our_basket", "2022-04-28", 13.0, -0.38, 0.85, ""),
    "BBAI": ("BigBear.ai", "our_basket", "2021-02-11", 4.8, -0.47, 0.90, ""),
    "SPCX": ("SpaceX", "our_basket", "2026-06-12", 362.0, -0.12, 0.60, ""),
    "NVDA": ("Nvidia", "universe", "2020-01-02", 192.0, -0.03, 0.38, "AIQ|ARTY|BOTZ|CHAT|IGPT"),
    "AVGO": ("Broadcom", "universe", "2020-01-02", 353.0, -0.05, 0.36, "AIQ|ARTY|CHAT"),
    "ORCL": ("Oracle", "universe", "2020-01-02", 294.0, -0.11, 0.42, "AIQ|CHAT"),
    "AMD": ("Advanced Micro Devices", "universe", "2020-01-02", 214.0, -0.14, 0.50, "AIQ|ARTY|CHAT|IGPT"),
    "TSM": ("Taiwan Semiconductor (ADR)", "universe", "2020-01-02", 288.0, -0.06, 0.34, "AIQ|ARTY"),
    "PLTR": ("Palantir", "universe", "2020-09-30", 171.0, -0.18, 0.62, "AIQ|ARTY|CHAT|IGPT"),
    "MU": ("Micron", "universe", "2020-01-02", 201.0, -0.08, 0.48, "AIQ|ARTY|IGPT"),
    "DELL": ("Dell Technologies", "universe", "2020-01-02", 118.0, -0.26, 0.44, "AIQ"),
    "ARM": ("Arm Holdings (ADR)", "universe", "2023-09-14", 131.0, -0.28, 0.58, "ARTY|CHAT"),
}


def days_listed(listing, d):
    # dummy approximation, as in the Phase 1 dummy rows: 252/365 of calendar days
    return max(1, int((d - date.fromisoformat(listing)).days * 252 / 365) + 1)


def write(name, rows):
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows")


# universe_members
write("universe_members.csv", [
    {
        "ticker": t, "company_name": v[0], "source_etfs": v[6], "n_source_etfs": len(v[6].split("|")),
        "listing_date": v[2], "snapshot_date": SNAPSHOT.isoformat(), "added_date": "2020-01-01",
        "removed_date": "", "added_reason": "etf_snapshot", "removed_reason": "",
        "notes": "DUMMY placeholder, not the selected universe",
    }
    for t, v in T.items() if v[1] == "universe"
])

# weekly_features and weekly_labels
features, labels = [], []
for i, d in enumerate(AS_OF):
    week = []
    for t, (name, role, listing, price, dd0, vol, _) in T.items():
        dl = days_listed(listing, d)
        if dl < 60:
            continue  # no row before 60 trading days of history
        dd = min(0.0, dd0 + random.uniform(-0.04, 0.04) * (2 - i))
        px = round(price * (1 + dd) / (1 + dd0), 2)
        screened = dl >= 126  # history, price and liquidity screen (dummy prices and ADV all pass)
        r = {
            "as_of": d.isoformat(), "ticker": t, "role": role, "adj_close": px, "days_listed": dl,
            "adv_20d_usd": round(random.uniform(0.2, 9.0) * 1e8, 0),
            "drawdown_252": round(dd, 4),
            "ret_20d": round(random.uniform(-0.18, 0.12), 4),
            "ret_60d": round(random.uniform(-0.30, 0.25), 4),
            "ret_120d": round(random.uniform(-0.35, 0.60), 4) if dl > 120 else "",
            "vol_60d": round(vol * random.uniform(0.9, 1.1), 4),
            "volume_ratio_60d": round(random.uniform(0.7, 1.6), 3),
            "beta_spx_120d": round(random.uniform(1.0, 2.6), 3) if dl > 120 else "",
            "beta_arkk_120d": round(random.uniform(0.7, 1.9), 3) if dl > 120 else "",
            "days_listed_capped": min(dl, 1260),
            "spx_distance": [-0.012, -0.021, -0.018][i],
            "credit_distance": [-0.004, -0.011, -0.009][i],
            "is_screen_eligible": str(screened).lower(),
            "universe_breadth": None,
            "is_model_eligible": str(screened).lower(),
            "computed_at": NOW,
        }
        week.append(r)
    univ = [r for r in week if r["role"] == "universe" and r["is_screen_eligible"] == "true"]
    breadth = round(sum(r["drawdown_252"] <= -0.25 for r in univ) / len(univ), 4)
    for r in week:
        r["universe_breadth"] = breadth
        final = SPLIT[d] == "test"
        fwd = round(random.uniform(-0.38, -0.02), 4) if final else ""
        labels.append({
            "as_of": r["as_of"], "ticker": r["ticker"], "role": r["role"],
            "fwd_days_available": 60 if final else [0, 5, 0][i],
            "fwd_min_adj_close": round(r["adj_close"] * (1 + fwd), 2) if final else "",
            "fwd_min_return": fwd,
            "label_drop_20pct_60d": int(fwd <= -0.20) if final else "",
            "label_status": "final" if final else "pending",
            "split": SPLIT[d], "computed_at": NOW,
        })
    features.extend(week)
write("weekly_features.csv", features)
write("weekly_labels.csv", labels)

# model_predictions: every model, every eligible row
preds = []
for r in features:
    if r["is_model_eligible"] != "true":
        continue
    base = min(0.92, max(0.03, 0.10 - 1.1 * r["drawdown_252"] + 0.25 * (r["vol_60d"] - 0.4)))
    for m in MODELS:
        p = min(0.97, max(0.01, base + random.uniform(-0.06, 0.06)))
        preds.append({
            "as_of": r["as_of"], "ticker": r["ticker"], "role": r["role"], "model_name": m,
            "model_version": "dummy-0", "trained_at": TRAINED, "prob_drop_20pct_60d": round(p, 3),
            "split": SPLIT[date.fromisoformat(r["as_of"])], "scored_at": NOW,
        })
write("model_predictions.csv", preds)

# model_scores: the served model only, latest two weeks
scores, prev = [], {}
for d in AS_OF[1:]:
    week = [p for p in preds if p["as_of"] == d.isoformat() and p["model_name"] == SERVED]
    univ = sorted((p["prob_drop_20pct_60d"] for p in week if p["role"] == "universe"), reverse=True)
    for p in sorted(week, key=lambda p: -p["prob_drop_20pct_60d"]):
        if p["role"] == "universe":
            rank = univ.index(p["prob_drop_20pct_60d"]) + 1
        else:
            rank = 1 + sum(u > p["prob_drop_20pct_60d"] for u in univ)
        scores.append({
            "ticker": p["ticker"], "as_of": p["as_of"],
            "prob_drop_20pct_60d": p["prob_drop_20pct_60d"], "rank_in_universe": rank,
            "model_version": "dummy-0", "trained_at": TRAINED, "model_name": SERVED, "role": p["role"],
            "universe_size": len(univ),
            "pct_rank_in_universe": round(min(1.0, rank / len(univ)), 4),
            "prob_change_1w": round(p["prob_drop_20pct_60d"] - prev[p["ticker"]], 3) if p["ticker"] in prev else "",
            "scored_at": NOW,
        })
    prev = {p["ticker"]: p["prob_drop_20pct_60d"] for p in week}
write("model_scores.csv", scores)

# model_evaluation: made-up metrics, shaped like the real report
AUC = {"baseline_drawdown": 0.61, "baseline_vol": 0.64, "logistic": 0.66, "boosted_trees": 0.65}
ev = []
for m in MODELS:
    for pop, n_rows in (("universe", 414), ("our_basket", 460)):
        shift = 0.0 if pop == "universe" else -0.03
        rows = [
            ("auc", AUC[m] + shift, 0.07), ("precision_top_decile", 0.41 + (AUC[m] - 0.61) + shift, 0.12),
            ("brier", 0.19 - (AUC[m] - 0.61) / 4, 0.03), ("mean_predicted", 0.27, 0.04), ("base_rate", 0.26, None),
        ]
        for metric, value, half in rows:
            ev.append({
                "model_name": m, "model_version": "dummy-0", "trained_at": TRAINED, "split": "test", "population": pop,
                "metric": metric, "value": round(value, 3),
                "ci_low": round(value - half, 3) if half else "",
                "ci_high": round(value + half, 3) if half else "",
                "n_rows": n_rows, "n_weeks": 46,
                "beats_best_baseline": "false" if metric == "auc" and m in ("logistic", "boosted_trees") and pop == "universe" else "",
                "evaluated_at": NOW,
            })
write("model_evaluation.csv", ev)

# universe_dial_daily: three days, universe dial one level below the official dial
dial = []
for d, (valid, broken, med) in zip(
    [date(2026, 11, 11), date(2026, 11, 12), date(2026, 11, 13)],
    [(118, 41, -0.13), (118, 43, -0.14), (118, 42, -0.14)],
):
    dial.append({
        "trade_date": d.isoformat(), "univ_members_valid": valid, "univ_members_broken": broken,
        "universe_breadth": round(broken / valid, 4), "universe_median_drawdown": med,
        "cond_divergence": "false", "is_armed": "false", "armed_since": "",
        "universe_dial_level": 0, "universe_dial_label": "CALM", "official_dial_level": 2,
        "dials_agree": "false", "computed_at": NOW,
    })
write("universe_dial_daily.csv", dial)
