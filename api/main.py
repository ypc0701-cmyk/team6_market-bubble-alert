"""Model API for Phase 2 (issue #89).

Serves the latest week of marts.model_scores (schema contract v0.3, section 5 item 10):
  GET /risk?ticker=NVDA  one stock
  GET /basket            our speculative basket, with today's dial

DATA_SOURCE=dummy (default) serves api/dummy_scores.csv, a copy of the contract's
dummy rows (docs/dummy_rows/phase2/model_scores.csv), so the API can be built and
called before the model exists. DATA_SOURCE=bigquery reads the warehouse.
Every response says which source it came from, so dummy numbers are never mistaken
for model output.
"""

import csv
import datetime as dt
import os
import re
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

DATA_SOURCE = os.environ.get("DATA_SOURCE", "dummy")
PROJECT = os.environ.get("BQ_PROJECT", "market-bubble-alert")
MARTS = os.environ.get("MARTS_DATASET", f"{PROJECT}.marts")
CACHE_SECONDS = int(os.environ.get("CACHE_SECONDS", "600"))

DUMMY_FILE = Path(__file__).with_name("dummy_scores.csv")
# Dummy mode only: the active speculative roster in dbt/seeds/basket_members.csv,
# used to report basket names without a score. In bigquery mode this comes from
# marts.basket_members.
DUMMY_BASKET = ["CRWV", "NBIS", "IREN", "APLD", "WULF", "CIFR", "SMCI", "AI", "SOUN", "BBAI", "SPCX"]

TICKER_RE = re.compile(r"^[A-Z0-9.^\-]{1,10}$")

# model_scores columns from schema contract v0.3
SCORE_COLUMNS = [
    "ticker", "as_of", "prob_drop_20pct_60d", "rank_in_universe", "model_version",
    "trained_at", "model_name", "role", "universe_size", "pct_rank_in_universe",
    "prob_change_1w", "scored_at",
]

SCORES_SQL = f"""
SELECT {", ".join(SCORE_COLUMNS)}
FROM `{MARTS}.model_scores`
WHERE as_of = (SELECT MAX(as_of) FROM `{MARTS}.model_scores`)
"""

BASKET_SQL = f"""
SELECT ticker
FROM `{MARTS}.basket_members`
WHERE basket = 'speculative' AND removed_date IS NULL
"""

DIAL_SQL = f"""
SELECT trade_date AS as_of, dial_level, dial_label
FROM `{MARTS}.daily_signals`
ORDER BY trade_date DESC
LIMIT 1
"""

app = FastAPI(
    title="Market Bubble Early Warning: model API",
    description="Probability that a stock falls 20% or more within the next 60 trading days.",
    version="0.2.0",
)

_cache = {"loaded_at": 0.0, "data": None}


def _clean(row):
    """JSON-ready values: dates and timestamps as ISO strings, numbers typed."""
    out = {}
    for key in SCORE_COLUMNS:
        value = row.get(key)
        if value in ("", None):
            value = None
        elif isinstance(value, (dt.date, dt.datetime)):
            value = value.isoformat()
        elif key in ("prob_drop_20pct_60d", "pct_rank_in_universe", "prob_change_1w"):
            value = float(value)
        elif key in ("rank_in_universe", "universe_size"):
            value = int(value)
        out[key] = value
    return out


def _load_dummy():
    with open(DUMMY_FILE, newline="") as f:
        rows = list(csv.DictReader(f))
    latest = max(r["as_of"] for r in rows)
    scores = {r["ticker"]: _clean(r) for r in rows if r["as_of"] == latest}
    dial = {"as_of": latest, "dial_level": 2, "dial_label": "DIVERGENCE"}
    return scores, DUMMY_BASKET, dial


def _load_bigquery():
    from google.cloud import bigquery  # imported here so dummy mode needs no GCP

    client = bigquery.Client(project=PROJECT)
    scores = {row["ticker"]: _clean(dict(row)) for row in client.query(SCORES_SQL).result()}
    basket = [row["ticker"] for row in client.query(BASKET_SQL).result()]
    dial_rows = [dict(r) for r in client.query(DIAL_SQL).result()]
    dial = None
    if dial_rows:
        dial = {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in dial_rows[0].items()}
    return scores, basket, dial


LOADERS = {"dummy": _load_dummy, "bigquery": _load_bigquery}


def get_data():
    """Scores, basket roster and dial, cached so repeated calls do not re-query BigQuery."""
    now = time.time()
    if _cache["data"] is None or now - _cache["loaded_at"] > CACHE_SECONDS:
        _cache["data"] = LOADERS[DATA_SOURCE]()
        _cache["loaded_at"] = now
    return _cache["data"]


def _with_context(score, dial):
    return {
        **score,
        "in_our_basket": score["role"] == "our_basket",
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
    scores, _, _ = get_data()
    as_of = next(iter(scores.values()))["as_of"] if scores else None
    return {"status": "ok", "data_source": DATA_SOURCE, "as_of": as_of, "scored_tickers": len(scores)}


@app.get("/risk")
def risk(ticker: str = Query(..., description="Ticker symbol, e.g. NVDA")):
    ticker = ticker.strip().upper()
    if not TICKER_RE.match(ticker):
        raise HTTPException(status_code=422, detail="Invalid ticker format")
    scores, _, dial = get_data()
    if ticker not in scores:
        raise HTTPException(
            status_code=404,
            detail=f"{ticker} is not scored this week. GET /basket lists our stocks.",
        )
    return _with_context(scores[ticker], dial)


@app.get("/basket")
def basket():
    scores, roster, dial = get_data()
    stocks = [_with_context(s, dial) for s in scores.values() if s["role"] == "our_basket"]
    stocks.sort(key=lambda s: s["prob_drop_20pct_60d"], reverse=True)
    universe = sorted(s["prob_drop_20pct_60d"] for s in scores.values() if s["role"] == "universe")
    any_row = next(iter(scores.values()), None)
    return {
        "as_of": any_row["as_of"] if any_row else None,
        "model_name": any_row["model_name"] if any_row else None,
        "model_version": any_row["model_version"] if any_row else None,
        "trained_at": any_row["trained_at"] if any_row else None,
        "universe_size": any_row["universe_size"] if any_row else None,
        "universe_median_prob": universe[len(universe) // 2] if universe else None,
        "dial_level": dial["dial_level"] if dial else None,
        "dial_label": dial["dial_label"] if dial else None,
        "missing_from_scores": sorted(t for t in roster if t not in scores),
        "stocks": stocks,
        "data_source": DATA_SOURCE,
    }
