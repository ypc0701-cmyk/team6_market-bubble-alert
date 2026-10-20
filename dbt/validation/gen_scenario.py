"""Synthetic prices_raw for validating the Lane 3 marts.

Seven years of trading days from the backfill start. The scenario walks the dial through every
level and every armed_state_change value, exercises the young-listing rules with the real seed's
listing dates (NBIS lists 14 days in, SPCX lists ~430 days in with an IPO pop), and drops one
price row so "missing day" handling is covered. Numbers are shaped, not real.

Timeline (t = trading-day index, 1-based):
  1-150     calm, everything rising
  151-200   speculative tier breaks (9 of 10 broken), S&P at highs  -> divergence from ~165, held ~179
  201-215   pause: breadth ~0.4 (no close, not divergence)
  216-260   strict divergence
  261-290   S&P -7%                                                  -> TOPPING
  291-330   S&P -13%, mega median -18%, credit watch, concentration -6% -> REPRICING
  331-360   S&P -24%, breadth >= 0.9, credit stress                  -> WASHOUT
  361-420   recovery; breadth < 0.3 at ~380 closes episode 1; S&P -8% -> TOPPING
  421-499   quiet, S&P at highs                                      -> DIVERGENCE (level 2)
  500-530   divergence episode 2 while armed                         -> 'rearmed' at ~514
  531-545   breadth falls, episode 2 closes
  546-~893  quiet; 378th quiet day since episode 2 start             -> 'disarmed_quiet'
  ~894-949  unarmed CALM, with a credit-only stress spell (905-925) -> STRAIN + credit_only badge
  950-980   divergence episode 3                                     -> 'armed' at ~964
  981-999   episode 3 closes
  1000-1800 S&P grinds down 8%/yr (never quiet)                      -> TOPPING until the 36-month ceiling -> 'disarmed_ceiling'
  1200      SMCI removed from the speculative basket (no_longer_ai_story) -> roster_changed_today, in_force 10
  1800      partial load (four tickers missing)                       -> held back from every mart

Also writes basket_members_scenario.csv: the real seed plus the SMCI removal. Run the oracle and the
marts against that seed (load_duck.py takes it as a third argument) so the roster logic is exercised.
"""
import csv
import math
import pathlib
import random
import sys
from datetime import date, timedelta

random.seed(882)
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).parent
SEED = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path(__file__).parent / "basket_members.csv"
N = 1800

# trading calendar: weekdays from 2024-10-01, a handful of holidays dropped
cal, d = [], date(2024, 10, 1)
while len(cal) < N:
    if d.weekday() < 5 and not (d.month == 12 and d.day == 25) and not (d.month == 1 and d.day == 1) and not (d.month == 7 and d.day == 4):
        cal.append(d)
    d += timedelta(days=1)
tidx = {dd: i + 1 for i, dd in enumerate(cal)}

members = list(csv.DictReader(open(SEED)))
listing = {m["ticker"]: date.fromisoformat(m["listing_date"]) for m in members}
basket = {m["ticker"]: m["basket"] for m in members}


def path(points, noise=0.0):
    """Piecewise-linear level over t=1..N from (t, level) breakpoints, times a mild noise."""
    levels = []
    pts = sorted(points)
    for t in range(1, N + 1):
        for (t0, l0), (t1, l1) in zip(pts, pts[1:]):
            if t0 <= t <= t1:
                lv = l0 + (l1 - l0) * (t - t0) / (t1 - t0) if t1 > t0 else l1
                break
        else:
            lv = pts[-1][1] if t > pts[-1][0] else pts[0][1]
        levels.append(lv * (1 + random.uniform(-noise, noise)))
    return levels


spx = path([(1, 1.00), (150, 1.10), (260, 1.12), (290, 1.04), (330, 0.97), (360, 0.85), (420, 1.03),
            (470, 1.14), (499, 1.15), (700, 1.22), (893, 1.30), (1000, 1.34),
            (1800, 1.34 * 0.92 ** (800 / 252))], 0.002)
# megas: small moves except the repricing leg
mega = path([(1, 1.00), (150, 1.15), (290, 1.13), (300, 0.95), (360, 0.94), (420, 1.10), (1800, 2.0)], 0.004)
# speculative archetypes. "deep" breaks hard, "pause" recovers in the pause, "resilient" barely breaks.
deep = path([(1, 1.0), (150, 1.6), (165, 1.05), (200, 1.0), (215, 1.0), (260, 0.9), (330, 0.7), (360, 0.6),
             (380, 1.5), (420, 1.7), (470, 1.9), (499, 1.95), (500, 1.5), (530, 1.3), (545, 1.9), (893, 2.3),
             (949, 2.6), (950, 1.9), (980, 1.6), (999, 2.7), (1800, 3.0)], 0.006)
pause = path([(1, 1.0), (150, 1.6), (165, 1.05), (200, 1.0), (205, 1.3), (215, 1.3), (225, 0.95), (330, 0.7),
              (360, 0.6), (380, 1.5), (420, 1.7), (470, 1.9), (499, 1.95), (500, 1.5), (530, 1.3), (545, 1.9),
              (893, 2.3), (949, 2.6), (950, 1.9), (980, 1.6), (999, 2.7), (1800, 3.0)], 0.006)
resilient = path([(1, 1.0), (150, 1.6), (200, 1.5), (330, 1.5), (345, 1.05), (360, 1.0), (380, 1.6), (420, 1.7),
                  (470, 1.9), (499, 1.95), (545, 1.9), (893, 2.3), (949, 2.6), (999, 2.7), (1800, 3.0)], 0.006)
spec_shape = {"CRWV": deep, "IREN": deep, "APLD": deep, "WULF": deep, "CIFR": pause, "SMCI": pause, "AI": pause,
              "SOUN": pause, "BBAI": pause, "NBIS": resilient, "SPCX": deep}
# SPCX: IPO pop in its first 20 days, then settles; we splice this on top of its shape
# credit: HYG/IEF ratio via HYG level with IEF flat-ish
hyg = path([(1, 1.0), (290, 1.05), (300, 1.008), (330, 1.008), (335, 0.97), (360, 0.96), (420, 1.05), (895, 1.2), (905, 1.11), (925, 1.11), (940, 1.2), (1800, 1.3)], 0.001)
ief = path([(1, 1.0), (1800, 1.05)], 0.001)
spy = path([(1, 1.0), (1800, 1.4)], 0.001)
# concentration ratio SPY/RSP: breaks (-6%) during 300-330
rsp = [s / r for s, r in zip(spy, path([(1, 1.0), (295, 1.0), (300, 0.94), (330, 0.94), (340, 1.0), (1800, 1.0)], 0.001))]
arkk = path([(1, 1.0), (150, 1.4), (200, 1.0), (360, 0.8), (470, 1.5), (1800, 2.2)], 0.004)

base = {"MSFT": 400, "GOOGL": 170, "META": 550, "AMZN": 190, "NVDA": 120, "AVGO": 170, "ORCL": 160,
        "^GSPC": 5700, "ARKK": 50, "HYG": 79, "IEF": 94, "SPY": 570, "RSP": 175,
        "CRWV": 40, "NBIS": 20, "IREN": 10, "APLD": 7, "WULF": 5, "CIFR": 4, "SMCI": 40, "AI": 25, "SOUN": 5,
        "BBAI": 2, "SPCX": 300}

rows = []
for t, dd in enumerate(cal, start=1):
    for tk in base:
        if listing[tk] > dd:
            continue
        if tk == "IREN" and t == 250:
            continue  # a missing price row on an old day: stays a trading day, IREN just is not valid data
        if t == N and tk in ("NVDA", "SOUN", "HYG", "RSP"):
            continue  # partial load on the newest day: the whole day is held back until the next run
        if basket[tk] == "megacap":
            lv = mega[t - 1]
        elif tk == "^GSPC":
            lv = spx[t - 1]
        elif tk == "HYG":
            lv = hyg[t - 1]
        elif tk == "IEF":
            lv = ief[t - 1]
        elif tk == "SPY":
            lv = spy[t - 1]
        elif tk == "RSP":
            lv = rsp[t - 1]
        elif tk == "ARKK":
            lv = arkk[t - 1]
        else:
            lv = spec_shape[tk][t - 1]
            if tk == "SPCX":
                k = t - tidx[listing[tk]] + 1  # days listed
                if k <= 20:
                    lv *= 1.6 - 0.03 * k      # IPO pop that must not become the yardstick
        px = round(base[tk] * lv, 4)
        rows.append({
            "trade_date": dd.isoformat(), "ticker": tk,
            "open": px, "high": round(px * 1.01, 4), "low": round(px * 0.99, 4), "close": px, "adj_close": px,
            "volume": "" if tk.startswith("^") else 1000000, "source": "yfinance",
            "ingested_at": "2026-10-14T01:00:00+00:00", "run_id": "",
        })

OUT.mkdir(parents=True, exist_ok=True)
# scenario seed: the real roster plus one removal, so roster_changed_today and in_force are exercised
with open(OUT / "basket_members_scenario.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(members[0].keys()))
    w.writeheader()
    for m in members:
        row = dict(m)
        if m["ticker"] == "SMCI":
            row["removed_date"] = cal[1199].isoformat()
            row["removed_reason"] = "no_longer_ai_story"
            row["notes"] = "scenario: removed on trading day 1200"
        w.writerow(row)
with open(OUT / "prices_raw.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} rows, {len(cal)} trading days, {cal[0]} to {cal[-1]}")
