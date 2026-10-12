"""Generate internally consistent dummy rows for every contract table.

Scenario: three trading days (2026-10-05, 06, 07). The system is armed since 2026-02-11
(episode EP-2026-02-11, held on 2026-03-04), the S&P sits within 5% of its high, so the dial reads
Level 2 DIVERGENCE. Numbers are plausible, not real. Lane 4 builds the skeleton against these;
Lane 1 and 2 use them as the load shape.
"""
import csv, random, statistics, pathlib
from datetime import date, datetime, timezone

random.seed(882)
OUT = pathlib.Path(__file__).parent / "dummy_rows"
OUT.mkdir(exist_ok=True)
DATES = [date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)]
NOW = datetime(2026, 10, 8, 1, 0, tzinfo=timezone.utc).isoformat()

members = list(csv.DictReader(open(pathlib.Path(__file__).parent / "dbt/seeds/basket_members.csv")))
# (reference_high, drawdown on day 1) per ticker
base = {
    "CRWV": (187.0, -0.42), "NBIS": (141.0, -0.08), "IREN": (38.0, -0.31), "APLD": (22.5, -0.27),
    "WULF": (12.4, -0.36), "CIFR": (9.8, -0.29), "SMCI": (66.0, -0.33), "AI": (31.0, -0.44),
    "SOUN": (21.0, -0.38), "BBAI": (9.1, -0.47), "SPCX": (412.0, -0.12),
    "MSFT": (540.0, -0.04), "GOOGL": (255.0, -0.02), "META": (790.0, -0.09), "AMZN": (248.0, -0.06),
    "NVDA": (198.0, -0.03), "AVGO": (372.0, -0.05), "ORCL": (330.0, -0.11),
    "^GSPC": (6912.0, -0.018), "ARKK": (88.0, -0.21), "HYG": (82.0, -0.01), "IEF": (97.5, -0.004),
    "SPY": (689.0, -0.017), "RSP": (196.0, -0.012),
}
listing = {m["ticker"]: date.fromisoformat(m["listing_date"]) for m in members}
basket = {m["ticker"]: m["basket"] for m in members}

def trading_days_since(listing_date, d):
    # dummy approximation: 252/365 of calendar days, floor at 1
    return max(1, int((d - listing_date).days * 252 / 365) + 1)

prices, drawdowns = [], []
state = {}
for i, d in enumerate(DATES):
    for t, (high, dd0) in base.items():
        dd = dd0 + random.uniform(-0.015, 0.015) * i
        dd = min(0.0, dd)
        close = round(high * (1 + dd), 2)
        prices.append({
            "trade_date": d, "ticker": t, "open": round(close * 0.995, 2), "high": round(close * 1.01, 2),
            "low": round(close * 0.985, 2), "close": close, "adj_close": close,
            "volume": "" if t == "^GSPC" else random.randint(1_000_000, 60_000_000),
            "source": "yfinance", "ingested_at": NOW, "run_id": f"scheduled__{d.isoformat()}T22:00:00+00:00",
        })
        dl = trading_days_since(listing[t], d)
        win = 0 if dl <= 20 else min(252, dl - 20)
        ref = None if win == 0 else high
        drawdown = None if ref is None else round(close / ref - 1, 6)
        mature = dl >= 60
        eligible = mature and drawdown is not None and basket[t] in ("speculative", "megacap")
        drawdowns.append({
            "trade_date": d, "ticker": t, "basket": basket[t], "adj_close": close, "days_listed": dl,
            "reference_window_days": win, "reference_high": ref, "drawdown": drawdown,
            "is_mature": mature, "is_signal_eligible": eligible,
            "is_broken": "" if drawdown is None else (drawdown <= -0.25),
            "return_6m": round(random.uniform(-0.5, 2.1), 4) if dl > 126 else "", "computed_at": NOW,
        })
        state[(d, t)] = (close, drawdown, eligible)

signals, credit = [], []
for d in DATES:
    spec = [state[(d, t)] for t in base if basket[t] == "speculative"]
    valid = [s for s in spec if s[2]]
    broken = [s for s in valid if s[1] <= -0.25]
    breadth = len(broken) / len(valid)
    spec_med = statistics.median(s[1] for s in valid)
    mega = [state[(d, t)] for t in base if basket[t] == "megacap"]
    mega_med = statistics.median(s[1] for s in mega)
    spx_close, spx_dd, _ = state[(d, "^GSPC")]
    conc = state[(d, "SPY")][0] / state[(d, "RSP")][0]
    conc_high = conc * 1.012
    conc_dist = conc / conc_high - 1
    ratio = state[(d, "HYG")][0] / state[(d, "IEF")][0]
    ratio_high = ratio * 1.008
    cdist = ratio / ratio_high - 1
    cstatus = "normal" if cdist > -0.03 else ("watch" if cdist > -0.06 else "stress")
    credit.append({
        "trade_date": d, "hyg_adj_close": state[(d, "HYG")][0], "ief_adj_close": state[(d, "IEF")][0],
        "credit_ratio": round(ratio, 6), "ratio_window_days": 126, "ratio_high_126": round(ratio_high, 6),
        "credit_distance": round(cdist, 6), "credit_status": cstatus, "fred_hy_oas": 3.41, "computed_at": NOW,
    })
    cond_div = breadth >= 0.5 and spec_med <= -0.15 and spx_dd > -0.05
    cond_strict = breadth >= 0.7 and spec_med <= -0.25 and spx_dd > -0.05
    det_spx = spx_dd <= -0.05
    det_conc = conc_dist <= -0.05
    det_credit = cstatus == "stress"
    det = det_spx or det_conc or det_credit
    rep = spx_dd <= -0.10 and (mega_med <= -0.15 or det_conc)
    wash = spx_dd <= -0.20 and breadth >= 0.90 and det_credit
    quiet = not (det or rep or wash)
    armed = True
    if wash: lvl = 5
    elif armed and rep: lvl = 4
    elif armed and det: lvl = 3
    elif armed and spx_dd > -0.05: lvl = 2
    elif cond_div or cstatus != "normal" or armed or det or rep: lvl = 1
    else: lvl = 0
    label = ["CALM", "STRAIN", "DIVERGENCE", "TOPPING", "REPRICING", "WASHOUT"][lvl]
    run = 0 if not cond_div else 7 + DATES.index(d)
    signals.append({
        "trade_date": d, "spec_members_in_force": 11, "spec_members_valid": len(valid),
        "spec_members_broken": len(broken), "breadth": round(breadth, 6), "spec_median_drawdown": round(spec_med, 6),
        "roster_changed_today": False, "mega_members_valid": 7, "mega_median_drawdown": round(mega_med, 6),
        "spx_adj_close": spx_close, "spx_reference_high": base["^GSPC"][0], "spx_distance": spx_dd,
        "concentration_ratio": round(conc, 6), "concentration_high_126": round(conc_high, 6),
        "concentration_distance": round(conc_dist, 6), "is_concentration_broken": det_conc,
        "credit_distance": round(cdist, 6), "credit_status": cstatus,
        "arkk_drawdown": state[(d, "ARKK")][1], "basket_audit_flag": abs(state[(d, "ARKK")][1] - spec_med) >= 0.15,
        "cond_divergence": cond_div, "cond_divergence_strict": cond_strict, "det_spx_band": det_spx,
        "det_concentration": det_conc, "det_credit_stress": det_credit, "cond_deterioration": det,
        "cond_repricing": rep, "cond_washout": wash,
        "divergence_run_days": run, "is_held_today": run >= 15, "episode_id": "EP-2026-09-29" if cond_div else "",
        "is_quiet_day": quiet, "is_armed": armed, "armed_since": date(2026, 2, 11), "armed_episode_id": "EP-2026-02-11",
        "quiet_days_used": 150 + DATES.index(d), "armed_ceiling_date": date(2029, 2, 11), "armed_state_change": "",
        "dial_level": lvl, "dial_label": label, "badge": "",
        "dial_explanation": f"{label}: armed since 2026-02-11; {len(broken)} of {len(valid)} speculative names broken; S&P {abs(spx_dd)*100:.1f}% off its high.",
        "computed_at": NOW,
    })

episodes = [{
    "episode_id": "EP-2026-02-11", "start_date": date(2026, 2, 11), "end_date": date(2026, 5, 19), "is_open": False,
    "trading_days": 68, "divergence_days": 41, "max_divergence_run": 23, "is_held": True, "held_date": date(2026, 3, 4),
    "max_breadth": 0.8182, "min_spec_median_drawdown": -0.3315, "strict_days": 9,
    "armed_since": date(2026, 2, 11), "armed_ceiling_date": date(2029, 2, 11), "quiet_expiry_date": "",
    "disarm_date": "", "disarm_reason": "", "computed_at": NOW,
}, {
    "episode_id": "EP-2026-09-29", "start_date": date(2026, 9, 29), "end_date": "", "is_open": True,
    "trading_days": 9, "divergence_days": 9, "max_divergence_run": 9, "is_held": False, "held_date": "",
    "max_breadth": 0.7273, "min_spec_median_drawdown": -0.31, "strict_days": 2,
    "armed_since": "", "armed_ceiling_date": "", "quiet_expiry_date": "", "disarm_date": "", "disarm_reason": "",
    "computed_at": NOW,
}]

def dump(name, rows):
    with open(OUT / f"{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    print(name, len(rows), "rows")

dump("prices_raw", prices)
dump("daily_drawdowns", drawdowns)
dump("credit_daily", credit)
dump("daily_signals", signals)
dump("episodes", episodes)
