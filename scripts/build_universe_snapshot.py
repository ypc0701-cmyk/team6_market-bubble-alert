"""Build the universe_members seed file from the Nov 23, 2026 ETF snapshot (decision R1).

Inputs (committed next to this script's output, in docs/universe_snapshot_2026-11-23/):
  etf_screen.csv     every AI-named ETF considered, with issuer net assets and whether it qualifies
  yahoo_screen.csv   every NYSE/Nasdaq-style holding of a candidate ETF, with Yahoo price data
                     as of the Nov 23 close (exchange, listing date, close, 60-day dollar volume)

The raw issuer holdings files are not committed: Global X and BlackRock prohibit redistribution.
Their URLs and as-of dates are in etf_screen.csv; candidate_etfs records which fund held what.

Output: docs/universe_snapshot_2026-11-23/universe_members.csv, copied into dbt/seeds/ by the
Lane 2 seed PR (#74) together with its tests and the sources.yml relationships change.

Usage:
  python scripts/build_universe_snapshot.py               # funds with qualifies == yes
  python scripts/build_universe_snapshot.py --include IGPT
"""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "docs" / "universe_snapshot_2026-11-23"
SNAPSHOT_DATE = "2026-11-23"
US_EXCHANGES = {"NMS", "NGM", "NCM", "NYQ"}  # Nasdaq GS/GM/CM, NYSE. NYSE American (ASE) is not NYSE.
# Foreign holdings whose local ticker collides with a different US-listed company on Yahoo.
TICKER_COLLISIONS = {
    "DSY": "IGPT holds Dassault Systemes (Paris); DSY on Nasdaq is Big Tree Cloud",
    "NXT": "IGPT holds NEXTDC (ASX); NXT on Nasdaq is Nextpower",
    "NEM": "IGPT holds Nemetschek (Xetra); NEM on NYSE is Newmont",
}


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include", nargs="*", default=[], help="ETFs marked pending to treat as qualifying")
    args = ap.parse_args()

    etfs = read(SNAP / "etf_screen.csv")
    qualifying = {e["etf"] for e in etfs if e["qualifies"] == "yes"} | set(args.include)
    speculative = {r["ticker"] for r in read(ROOT / "dbt" / "seeds" / "basket_members.csv")
                   if r["basket"] == "speculative"}

    screen_out, seed = [], []
    for r in read(SNAP / "yahoo_screen.csv"):
        t = r["ticker"]
        src = sorted(set(r["candidate_etfs"].split("|")) & qualifying)
        close, adv = float(r["close_2026_11_23"]), float(r["adv60_usd_m"]) * 1e6
        reasons = []
        if not src:
            reasons.append("held only by non-qualifying ETFs")
        if t in TICKER_COLLISIONS:
            reasons.append("ticker collision: " + TICKER_COLLISIONS[t])
        if r["yahoo_exchange"] not in US_EXCHANGES:
            reasons.append(f"exchange {r['yahoo_exchange']} is not NYSE or Nasdaq")
        if r["instrument_type"] != "EQUITY":
            reasons.append("not an equity")
        if close <= 2:
            reasons.append(f"close {close:.2f} <= $2")
        if adv < 5e6:
            reasons.append(f"60-day dollar volume ${adv/1e6:.1f}M < $5M")
        if int(r["trading_days_since_2026_04_01"]) < 60:
            reasons.append("fewer than 60 trading days of history")
        if t in speculative:
            reasons.append("our speculative basket (R2)")
        passed = not reasons
        screen_out.append({"ticker": t, "yahoo_name": r["yahoo_name"],
                           "source_etfs": "|".join(src), "passes": "yes" if passed else "no",
                           "reason": "; ".join(reasons)})
        if passed:
            seed.append({
                "ticker": t, "company_name": r["yahoo_name"], "source_etfs": "|".join(src),
                "n_source_etfs": len(src), "listing_date": r["listing_date"],
                "snapshot_date": SNAPSHOT_DATE, "added_date": "2020-01-01", "removed_date": "",
                "added_reason": "etf_snapshot", "removed_reason": "", "notes": "",
            })

    seed.sort(key=lambda x: x["ticker"])
    cols = ["ticker", "company_name", "source_etfs", "n_source_etfs", "listing_date", "snapshot_date",
            "added_date", "removed_date", "added_reason", "removed_reason", "notes"]
    with open(SNAP / "universe_members.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(seed)
    with open(SNAP / "holdings_screen.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "yahoo_name", "source_etfs", "passes", "reason"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(screen_out, key=lambda x: (x["passes"] != "yes", x["ticker"])))
    print(f"qualifying ETFs: {sorted(qualifying)}")
    print(f"universe_members: {len(seed)} tickers; screened out: {len(screen_out) - len(seed)}")


if __name__ == "__main__":
    main()
