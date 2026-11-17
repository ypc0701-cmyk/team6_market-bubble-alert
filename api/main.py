"""Model API for Phase 2 (issue #89).

Serves the latest weekly drawdown-probability scores:
  GET /risk?ticker=NVDA  one stock
  GET /basket            our 11 speculative stocks, with today's dial

DATA_SOURCE=dummy (default) serves api/dummy_scores.csv so the API can be built and
called before the model exists. DATA_SOURCE=bigquery reads marts.model_scores.
Every response says which source it came from, so dummy numbers are never mistaken
for model output.

Column names in SCORES_SQL follow docs/phase2_proposal.md and must be aligned with
schema contract v0.3 (#79, #80) before switching to bigquery.
"""

import csv
import os
import re
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

DATA_SOURCE = os.environ.get("DATA_SOURCE", "dummy")
PROJECT = os.environ.get("BQ_PROJECT", "market-bubble-alert")
SCORES_TABLE = os.environ.get("SCORES_TABLE", f"{PROJECT}.marts.model_scores")
SIGNALS_TABLE = os.environ.get("SIGNALS_TABLE", f"{PROJECT}.marts.daily_signals")
CACHE_SECONDS = int(os.environ.get("CACHE_SECONDS", "600"))

# Active speculative roster in dbt/seeds/basket_members.csv on 2026-11-13.
# Replace with a basket_members lookup once contract v0.3 says where the API reads it.
OUR_BASKET = os.environ.get(
    "OUR_BASKET", "CRWV,NBIS,IREN,APLD,WULF,CIFR,SMCI,AI,SOUN,BBAI,SPCX"
).split(",")

DUMMY_FILE = Path(__file__).with_name("dummy_scores.csv")
TICKER_RE = re.compile(r"^[A-Z0-9.^\-]{1,10}$")

SCORES_SQL = f"""
SELECT ticker, CAST(as_of AS STRING) AS as_of, prob_drop_20pct_60d,
       rank_in_universe, model_version
FROM `{SCORES_TABLE}`
WHERE as_of = (SELECT MAX(as_of) FROM `{SCORES_TABLE}`)
"""

DIAL_SQL = f"""
SELECT CAST(trade_date AS STRING) AS as_of, dial_level, dial_label
FROM `{SIGNALS_TABLE}`
ORDER BY trade_date DESC
LIMIT 1
"""

app = FastAPI(
    title="Market Bubble Early Warning: model API",
    description="Probability that a stock falls 20% or more within the next 60 trading days.",
    version="0.1.0",
)

_cache = {"loaded_at": 0.0, "data": None}


def _load_dummy():
    with open(DUMMY_FILE, newline="") as f:
        rows = list(csv.DictReader(f))
    scores = {
        r["ticker"]: {
            "ticker": r["ticker"],
            "as_of": r["as_of"],
            "prob_drop_20pct_60d": float(r["prob_drop_20pct_60d"]),
            "rank_in_universe": int(r["rank_in_universe"]),
            "model_version": r["model_version"],
        }
        for r in rows
    }
    dial = {"as_of": rows[0]["as_of"], "dial_level": 2, "dial_label": "DIVERGENCE"}
    return scores, dial


def _load_bigquery():
    from google.cloud import bigquery  # imported here so dummy mode needs no GCP

    client = bigquery.Client(project=PROJECT)
    scores = {
        row["ticker"]: {
            "ticker": row["ticker"],
            "as_of": row["as_of"],
            "prob_drop_20pct_60d": float(row["prob_drop_20pct_60d"]),
            "rank_in_universe": int(row["rank_in_universe"]),
            "model_version": row["model_version"],
        }
        for row in client.query(SCORES_SQL).result()
    }
    dial_rows = list(client.query(DIAL_SQL).result())
    dial = dict(dial_rows[0]) if dial_rows else None
    return scores, dial


LOADERS = {"dummy": _load_dummy, "bigquery": _load_bigquery}


def get_data():
    """Scores and dial, cached so repeated calls do not re-query BigQuery."""
    now = time.time()
    if _cache["data"] is None or now - _cache["loaded_at"] > CACHE_SECONDS:
        _cache["data"] = LOADERS[DATA_SOURCE]()
        _cache["loaded_at"] = now
    return _cache["data"]


def _with_context(score, scores, dial):
    return {
        **score,
        "universe_size": len(scores),
        "in_our_basket": score["ticker"] in OUR_BASKET,
        "dial_level": dial["dial_level"] if dial else None,
        "dial_label": dial["dial_label"] if dial else None,
        "data_source": DATA_SOURCE,
    }


@app.get("/")
def root():
    return {
        "service": "market-bubble model API",
        "endpoints": ["/risk?ticker=NVDA", "/basket", "/health", "/docs"],
        "data_source": DATA_SOURCE,
    }


@app.get("/health")
def health():
    scores, _ = get_data()
    return {"status": "ok", "data_source": DATA_SOURCE, "scored_tickers": len(scores)}


@app.get("/risk")
def risk(ticker: str = Query(..., description="Ticker symbol, e.g. NVDA")):
    ticker = ticker.strip().upper()
    if not TICKER_RE.match(ticker):
        raise HTTPException(status_code=422, detail="Invalid ticker format")
    scores, dial = get_data()
    if ticker not in scores:
        raise HTTPException(
            status_code=404,
            detail=f"{ticker} is not scored this week. GET /basket lists our stocks.",
        )
    return _with_context(scores[ticker], scores, dial)


@app.get("/basket")
def basket():
    scores, dial = get_data()
    stocks = [_with_context(scores[t], scores, dial) for t in OUR_BASKET if t in scores]
    stocks.sort(key=lambda s: s["prob_drop_20pct_60d"], reverse=True)
    probs = sorted(s["prob_drop_20pct_60d"] for s in scores.values())
    median = probs[len(probs) // 2] if probs else None
    return {
        "as_of": stocks[0]["as_of"] if stocks else None,
        "dial_level": dial["dial_level"] if dial else None,
        "dial_label": dial["dial_label"] if dial else None,
        "universe_median_prob": median,
        "missing_from_scores": [t for t in OUR_BASKET if t not in scores],
        "stocks": stocks,
        "data_source": DATA_SOURCE,
    }
