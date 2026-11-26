# Phase 2 universe snapshot, 2026-11-23 (R1)

Snapshot date: Monday 2026-11-23, the first trading day after PR #99 (rules frozen) merged on 2026-11-22. Data pulled on 2026-11-24 from issuer sites and Yahoo; every figure below is as of the Nov 23 close unless stated.

Result: **6 qualifying ETFs, 141 tickers** in `universe_members.csv` (this folder), in the contract v0.3 columns. Lane 2 copies it into `dbt/seeds/` in #74 with the seed tests and the sources.yml relationships change, so the first universe load does not break `dbt build`. Rebuild with `python scripts/build_universe_snapshot.py`.

## Files

| File | What it holds |
|---|---|
| `etf_screen.csv` | Every AI-named ETF near the $1B line, with the issuer's net assets, as-of dates, source URL and the result |
| `yahoo_screen.csv` | Every NYSE/Nasdaq-style holding of a candidate ETF, with Yahoo exchange, listing date, Nov 23 close, 60-day average dollar volume and which candidate ETFs held it |
| `holdings_screen.csv` | Output of the build script: pass or fail per ticker, with the reason |

## Step 1: which ETFs qualify

Qualify (net assets on Nov 23): BAI $11.34B, AIQ $8.87B, ARTY $3.20B, BOTZ $2.68B, CHAT $1.42B, IGPT $1.10B.
Out: AGIX $877M, ALAI $773M, IVES $752M. AIPO, AIS and ROBT are far below $1B on aggregator figures.

Changes from the Nov 16 "expected" list: AGIX and IVES did not reach $1B. ALAI was checked because an aggregator listed it at $3.25B; Alger's own figure is $773M.

**IGPT.** On the snapshot date Invesco's site showed $985.4M dated Nov 20. Every other issuer reports as of the Nov 23 close, so IGPT is read the same way: 14.87M shares at the Nov 23 close (about $74) is about $1.10B. Decided by Javier on Nov 24. Confirmed on Nov 25 from Invesco's NAV history: $74.259056 on Nov 23 x 14.87M shares = **$1.104B**. IGPT stays in.

## Step 2: holdings to candidates

Dropped before the price screen, by rule: cash, money market funds, futures, private positions (BAI's OpenAI and Anthropic private lots), and securities whose held line trades outside the US (for example 2330 TT, 005930 KS, 700 HK). A company held only through a foreign line is out even if it also trades in the US: ARTY holds Camtek on Tel Aviv, so CAMT does not enter (Celestica enters through other funds).

Foreign holdings whose local ticker matches a different US company on Yahoo were dropped as collisions: DSY (Dassault vs Big Tree Cloud), NXT (NEXTDC vs Nextpower), NEM (Nemetschek vs Newmont). HEXAB, HLMA and IFCN have no US line.

## Step 3: price, liquidity and history screen (Nov 23)

Close above $2, 60-day average dollar volume of at least $5M, 60 trading days of history, NYSE or Nasdaq listing, then R2.

| Out | Why |
|---|---|
| KDK, RR | Close under $2 |
| EH | $2.8M a day |
| ANT | Listed Nov 19, 3 trading days |
| UMAC | NYSE American, which is not NYSE |
| SPCX, CRWV, SMCI, NBIS, AI, SOUN | Our speculative basket (R2) |

Share classes: only GOOGL and MOG-A are held, so no deduplication was needed.

## Deviations from R1 as written

1. **Holdings files are not committed.** Global X's file says it may not be reproduced or redistributed, and BlackRock's limits use to personal use. The repo keeps the source URL, the as-of date and, per ticker, which funds held it. Anyone can re-download from the URLs; issuers only serve the latest file, so the derived `candidate_etfs` column is the record.
2. **iShares holdings are dated Nov 20.** The latest file iShares served for BAI and ARTY on Nov 23 and 24 is as of Nov 20 (the prior trading day). It is used as the Nov 23 file.

## Data notes for Lane 1

- SNDK: Yahoo's daily history has no rows for Nov 20 and Nov 23 (the quote shows $87.71 on Nov 23). Check it after the backfill.
- ANT will become eligible for a later refresh only; it is not in this snapshot.
- 86 of the 141 names come from a single fund; 5 are held by five or six funds (AMD, MU, MRVL, NVDA, SNOW).
