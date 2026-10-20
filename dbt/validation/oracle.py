"""Reference implementation of the Lane 3 marts, written from the Methodology and the schema
contract in plain Python, independently of the dbt SQL. Where the SQL uses window functions and
arming intervals, this walks the calendar day by day with explicit state, so the two can disagree.

usage: python oracle.py prices_raw.csv basket_members.csv out_dir/
"""
import csv
import math
import pathlib
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta

prices_path, seed_path, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)

D = date.fromisoformat
members = list(csv.DictReader(open(seed_path)))
for m in members:
    m["listing_date"] = D(m["listing_date"])
    m["added_date"] = D(m["added_date"])
    m["removed_date"] = D(m["removed_date"]) if m["removed_date"] else None
bench = [m["ticker"] for m in members if m["basket"] == "benchmark"][0]

px = defaultdict(dict)  # ticker -> date -> adj_close
for r in csv.DictReader(open(prices_path)):
    px[r["ticker"]][D(r["trade_date"])] = float(r["adj_close"])

cal = sorted(px[bench])
# Partial loads: hold back the newest benchmark day while any in-force, listed ticker has no row on it.
def _in_force(d):
    return [m["ticker"] for m in members if m["added_date"] <= d and (m["removed_date"] is None or d < m["removed_date"]) and m["listing_date"] <= d]
if any(d not in px.get(tk, {}) for tk in _in_force(cal[-1]) for d in [cal[-1]]):
    cal = cal[:-1]
idx = {d: i for i, d in enumerate(cal)}  # 0-based
cal_start = cal[0]


def add_months(d, n):
    y, mth = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    last = (date(y + (mth == 12), (mth % 12) + 1, 1) - timedelta(days=1)).day
    return date(y, mth, min(d.day, last))


def span_for(ticker, d):
    for m in members:
        if m["ticker"] == ticker and m["added_date"] <= d and (m["removed_date"] is None or d < m["removed_date"]) and m["listing_date"] <= d:
            return m
    return None


# ---------------------------------------------------------------- daily_drawdowns
dd_rows = {}  # (date, ticker) -> row
for tk in px:
    m0 = [m for m in members if m["ticker"] == tk]
    if not m0:
        continue
    listing = m0[0]["listing_date"]
    if listing < cal_start:
        pre = math.floor((cal_start - listing).days * 252 / 365)
        first_i = 0
    else:
        pre = 0
        first_i = next(i for i, d in enumerate(cal) if d >= listing)
    for d in cal:
        m = span_for(tk, d)
        if m is None or d not in px[tk]:
            continue
        i = idx[d]
        days_listed = i - first_i + 1 + pre
        window = [px[tk][cal[j]] for j in range(max(0, i - 251), i + 1)
                  if cal[j] in px[tk] and (j - first_i + 1 + pre) > 20]
        ref = max(window) if window else None
        p = px[tk][d]
        dd = p / ref - 1 if ref else None
        p6 = px[tk].get(cal[i - 126]) if i - 126 >= 0 else None
        dd_rows[(d, tk)] = dict(
            trade_date=d, ticker=tk, basket=m["basket"], adj_close=p, days_listed=days_listed,
            reference_window_days=len(window), reference_high=ref, drawdown=dd,
            is_mature=days_listed >= 60,
            is_signal_eligible=days_listed >= 60 and dd is not None and m["basket"] in ("speculative", "megacap"),
            is_broken=(dd <= -0.25) if dd is not None else None,
            return_6m=(p / p6 - 1) if p6 else None,
        )

# ---------------------------------------------------------------- credit_daily
credit = {}
ratios = []
for i, d in enumerate(cal):
    if d not in px["HYG"] or d not in px["IEF"]:
        ratios.append(None)
        continue
    r = px["HYG"][d] / px["IEF"][d]
    ratios.append(r)
    win = [x for x in ratios[max(0, i - 125):i + 1] if x is not None]
    hi = max(win)
    dist = r / hi - 1
    status = "stress" if dist <= -0.06 else "watch" if dist <= -0.03 else "normal"
    credit[d] = dict(trade_date=d, hyg_adj_close=px["HYG"][d], ief_adj_close=px["IEF"][d], credit_ratio=r,
                     ratio_window_days=len(win), ratio_high_126=hi, credit_distance=dist, credit_status=status,
                     fred_hy_oas=None)


def median(xs):
    return statistics.median(xs) if xs else None


# ---------------------------------------------------------------- daily conditions
sig = {}
conc_hist = []
for i, d in enumerate(cal):
    spec = [r for (dd_, tk), r in dd_rows.items() if dd_ == d and r["basket"] == "speculative" and r["is_signal_eligible"]]
    mega = [r for (dd_, tk), r in dd_rows.items() if dd_ == d and r["basket"] == "megacap" and r["is_signal_eligible"]]
    in_force = sum(1 for m in members if m["basket"] == "speculative" and span_for(m["ticker"], d) is m)
    roster_changed = any(m["basket"] in ("speculative", "megacap") and (m["added_date"] == d or m["removed_date"] == d) for m in members)
    valid, broken = len(spec), sum(1 for r in spec if r["is_broken"])
    breadth = broken / valid if valid else None
    spec_med = median([r["drawdown"] for r in spec])
    mega_med = median([r["drawdown"] for r in mega])
    s = dd_rows[(d, bench)]
    conc = px["SPY"][d] / px["RSP"][d]
    conc_hist.append(conc)
    conc_hi = max(conc_hist[max(0, i - 125):i + 1])
    conc_dist = conc / conc_hi - 1
    cr = credit[d]
    arkk = dd_rows.get((d, "ARKK"), {}).get("drawdown")
    row = dict(
        trade_date=d, spec_members_in_force=in_force, spec_members_valid=valid, spec_members_broken=broken,
        breadth=breadth, spec_median_drawdown=spec_med, roster_changed_today=roster_changed,
        mega_members_valid=len(mega), mega_median_drawdown=mega_med,
        spx_adj_close=s["adj_close"], spx_reference_high=s["reference_high"], spx_distance=s["drawdown"],
        concentration_ratio=conc, concentration_high_126=conc_hi, concentration_distance=conc_dist,
        is_concentration_broken=conc_dist <= -0.05,
        credit_distance=cr["credit_distance"], credit_status=cr["credit_status"],
        arkk_drawdown=arkk,
        basket_audit_flag=(arkk is not None and spec_med is not None and abs(arkk - spec_med) >= 0.15),
    )
    spx = row["spx_distance"]
    row["cond_divergence"] = breadth is not None and breadth >= 0.5 and spec_med <= -0.15 and spx > -0.05
    row["cond_divergence_strict"] = breadth is not None and breadth >= 0.7 and spec_med <= -0.25 and spx > -0.05
    row["det_spx_band"] = spx <= -0.05
    row["det_concentration"] = row["is_concentration_broken"]
    row["det_credit_stress"] = cr["credit_status"] == "stress"
    row["cond_deterioration"] = row["det_spx_band"] or row["det_concentration"] or row["det_credit_stress"]
    row["cond_repricing"] = spx <= -0.10 and ((mega_med is not None and mega_med <= -0.15) or row["is_concentration_broken"])
    row["cond_washout"] = spx <= -0.20 and breadth is not None and breadth >= 0.9 and cr["credit_status"] == "stress"
    row["is_quiet_day"] = not (row["cond_deterioration"] or row["cond_repricing"] or row["cond_washout"])
    sig[d] = row

# ---------------------------------------------------------------- memory: a literal state machine
episodes = []        # dicts
open_ep = None
run = 0
armed_list = []      # held episodes with their arming interval state
prev_armed = False
for i, d in enumerate(cal):
    r = sig[d]
    run = run + 1 if r["cond_divergence"] else 0
    r["divergence_run_days"] = run
    r["is_held_today"] = run >= 15

    # episode open/close
    if open_ep is not None and r["breadth"] is not None and r["breadth"] < 0.30:
        open_ep["end_date"] = open_ep["last_day"]
        open_ep["is_open"] = False
        open_ep = None
    if open_ep is None and r["cond_divergence"]:
        open_ep = dict(start_date=d, end_date=None, is_open=True, trading_days=0, divergence_days=0,
                       max_divergence_run=0, is_held=False, held_date=None, max_breadth=None,
                       min_spec_median_drawdown=None, strict_days=0, armed_since=None, armed_ceiling_date=None,
                       quiet_expiry_date=None, disarm_date=None, disarm_reason=None, quiet_count=0,
                       last_day=None, disarm_pending=None)
        episodes.append(open_ep)
    if open_ep is not None:
        e = open_ep
        e["trading_days"] += 1
        e["divergence_days"] += r["cond_divergence"]
        e["max_divergence_run"] = max(e["max_divergence_run"], run)
        e["strict_days"] += r["cond_divergence_strict"]
        if r["breadth"] is not None:
            e["max_breadth"] = r["breadth"] if e["max_breadth"] is None else max(e["max_breadth"], r["breadth"])
        if r["spec_median_drawdown"] is not None:
            e["min_spec_median_drawdown"] = r["spec_median_drawdown"] if e["min_spec_median_drawdown"] is None else min(e["min_spec_median_drawdown"], r["spec_median_drawdown"])
        e["last_day"] = d
        if run >= 15 and not e["is_held"]:
            e["is_held"], e["held_date"], e["armed_since"] = True, d, e["start_date"]
            e["armed_ceiling_date"] = add_months(e["start_date"], 36)
            # quiet days from armed_since through today (today included below)
            e["quiet_count"] = sum(1 for j in range(idx[e["start_date"]], i) if sig[cal[j]]["is_quiet_day"])
            armed_list.append(e)
    r["episode_id"] = f"EP-{open_ep['start_date']}" if open_ep is not None else None

    # arming intervals: advance the quiet clock of every held episode, expire as needed
    held_event = None
    for e in armed_list:
        if e["disarm_date"] is not None and d >= e["disarm_date"]:
            continue
        if e["disarm_pending"] is not None and d >= e["disarm_pending"][0]:
            e["disarm_date"], e["disarm_reason"] = e["disarm_pending"]
            continue
        if e["held_date"] == d:
            held_event = e
        if e["quiet_expiry_date"] is None and d >= e["start_date"]:
            e["quiet_count"] += r["is_quiet_day"]
            if e["quiet_count"] >= 378:
                e["quiet_expiry_date"] = d
        # disarm on the first trading day on/after the ceiling, or the day after quiet expiry
        if d >= e["armed_ceiling_date"]:
            e["disarm_date"], e["disarm_reason"] = d, "ceiling"
        elif e["quiet_expiry_date"] is not None and d > e["quiet_expiry_date"]:
            e["disarm_date"], e["disarm_reason"] = d, "quiet_expiry"
    active = [e for e in armed_list if e["held_date"] <= d and (e["disarm_date"] is None or d < e["disarm_date"])]
    is_armed = bool(active)
    r["is_armed"] = is_armed
    if is_armed:
        a = max(active, key=lambda e: e["held_date"])
        r["armed_since"], r["armed_episode_id"] = a["start_date"], f"EP-{a['start_date']}"
        r["quiet_days_used"] = min(378, sum(1 for j in range(idx[a["start_date"]], i + 1) if sig[cal[j]]["is_quiet_day"]))
        r["armed_ceiling_date"] = a["armed_ceiling_date"]
    else:
        r["armed_since"] = r["armed_episode_id"] = r["quiet_days_used"] = r["armed_ceiling_date"] = None
    if held_event is not None:
        r["armed_state_change"] = "rearmed" if prev_armed else "armed"
    elif prev_armed and not is_armed:
        just = [e for e in armed_list if e["disarm_date"] == d]
        r["armed_state_change"] = "disarmed_quiet" if just[-1]["disarm_reason"] == "quiet_expiry" else "disarmed_ceiling"
    else:
        r["armed_state_change"] = None
    prev_armed = is_armed

    # the dial
    spx = r["spx_distance"]
    if r["cond_washout"]:
        lvl = 5
    elif is_armed and r["cond_repricing"]:
        lvl = 4
    elif is_armed and r["cond_deterioration"]:
        lvl = 3
    elif is_armed and spx > -0.05:
        lvl = 2
    elif r["cond_divergence"] or r["credit_status"] in ("watch", "stress") or is_armed or r["cond_deterioration"] or r["cond_repricing"]:
        lvl = 1
    else:
        lvl = 0
    r["dial_level"] = lvl
    r["dial_label"] = ["CALM", "STRAIN", "DIVERGENCE", "TOPPING", "REPRICING", "WASHOUT"][lvl]
    if not is_armed and (r["det_spx_band"] or r["det_concentration"] or r["cond_repricing"] or r["cond_washout"]):
        r["badge"] = "off_pattern"
    elif not is_armed and r["credit_status"] == "stress":
        r["badge"] = "credit_only"
    else:
        r["badge"] = None
    armed_txt = f"armed since {r['armed_since']}" if is_armed else "not armed"
    members_txt = f"{r['spec_members_broken']} of {r['spec_members_valid']} speculative names broken" if r["spec_members_valid"] else "no speculative member with valid data"
    badge_txt = {"off_pattern": " (off-pattern: decline without the junk-first precedent)",
                 "credit_only": " (credit-only: funding stress with no equity pattern)", None: ""}[r["badge"]]
    r["dial_explanation"] = f"{r['dial_label']}: {armed_txt}; {members_txt}; S&P {abs(spx) * 100:.1f}% off its high{badge_txt}."

# ---------------------------------------------------------------- write
def dump(name, rows, cols):
    with open(out / f"{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})

dump("daily_drawdowns", [dd_rows[k] for k in sorted(dd_rows)],
     ["trade_date", "ticker", "basket", "adj_close", "days_listed", "reference_window_days", "reference_high", "drawdown",
      "is_mature", "is_signal_eligible", "is_broken", "return_6m"])
dump("credit_daily", [credit[d] for d in cal if d in credit],
     ["trade_date", "hyg_adj_close", "ief_adj_close", "credit_ratio", "ratio_window_days", "ratio_high_126", "credit_distance", "credit_status", "fred_hy_oas"])
sig_cols = ["trade_date", "spec_members_in_force", "spec_members_valid", "spec_members_broken", "breadth", "spec_median_drawdown",
            "roster_changed_today", "mega_members_valid", "mega_median_drawdown", "spx_adj_close", "spx_reference_high", "spx_distance",
            "concentration_ratio", "concentration_high_126", "concentration_distance", "is_concentration_broken", "credit_distance",
            "credit_status", "arkk_drawdown", "basket_audit_flag", "cond_divergence", "cond_divergence_strict", "det_spx_band",
            "det_concentration", "det_credit_stress", "cond_deterioration", "cond_repricing", "cond_washout", "divergence_run_days",
            "is_held_today", "episode_id", "is_quiet_day", "is_armed", "armed_since", "armed_episode_id", "quiet_days_used",
            "armed_ceiling_date", "armed_state_change", "dial_level", "dial_label", "badge", "dial_explanation"]
dump("daily_signals", [sig[d] for d in cal], sig_cols)
for e in episodes:
    e["episode_id"] = f"EP-{e['start_date']}"
dump("episodes", episodes,
     ["episode_id", "start_date", "end_date", "is_open", "trading_days", "divergence_days", "max_divergence_run", "is_held", "held_date",
      "max_breadth", "min_spec_median_drawdown", "strict_days", "armed_since", "armed_ceiling_date", "quiet_expiry_date", "disarm_date", "disarm_reason"])

# coverage report
from collections import Counter
print("dial levels:", sorted(Counter(sig[d]["dial_level"] for d in cal).items()))
print("state changes:", [(str(d), sig[d]["armed_state_change"]) for d in cal if sig[d]["armed_state_change"]])
print("badges:", Counter(sig[d]["badge"] for d in cal))
print("episodes:", [(e["episode_id"], str(e["end_date"]), e["is_held"], str(e["held_date"]), str(e["disarm_date"]), e["disarm_reason"]) for e in episodes])
