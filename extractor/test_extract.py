"""Unit tests for the extractor's universe mode (#69). No network, no GCP: clients are faked.
Run from the repo root: python -m pytest extractor/test_extract.py -q"""
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest
from google.api_core.exceptions import NotFound

import extractor.extract as ex

BASKET = list(ex.TICKERS)                                  # the 24 Phase 1 symbols
UNIVERSE = ["NVDA", "AVGO", "ORCL", "AMD", "TSM", "PLTR", "MU", "DELL", "ARM"]  # dummy rows, #99


class FakeBQ:
    """Answers the member queries from a dict {table_suffix: list or exception}; records SQL."""
    def __init__(self, tables):
        self.tables, self.queries = tables, []

    def query(self, sql, job_config=None):
        self.queries.append((sql, job_config))
        for suffix, rows in self.tables.items():
            if suffix in sql:
                if isinstance(rows, Exception):
                    raise rows
                return SimpleNamespace(result=lambda rows=rows: [SimpleNamespace(ticker=t) for t in rows])
        return SimpleNamespace(result=lambda: [[0]])


def test_combine_drops_overlap_and_keeps_basket_first():
    out = ex.combine(BASKET, UNIVERSE)
    assert len(out) == 24 + 9 - 3          # NVDA, AVGO, ORCL are in both
    assert out[:24] == BASKET
    assert out[24:] == ["AMD", "TSM", "PLTR", "MU", "DELL", "ARM"]


def test_load_tickers_reads_both_tables(monkeypatch):
    fake = FakeBQ({"basket_members": BASKET, "universe_members": UNIVERSE})
    monkeypatch.setattr(ex.bigquery, "Client", lambda **k: fake)
    assert len(ex.load_tickers(date(2026, 11, 16), date(2026, 11, 20))) == 30
    assert all("SAFE_CAST(CAST(removed_date AS STRING) AS DATE) > @start" in q for q, _ in fake.queries)


def test_universe_not_seeded_loads_basket_only(monkeypatch):
    fake = FakeBQ({"basket_members": BASKET, "universe_members": NotFound("no table")})
    monkeypatch.setattr(ex.bigquery, "Client", lambda **k: fake)
    assert ex.load_tickers(date(2026, 11, 16), date(2026, 11, 20)) == BASKET


def test_basket_unreadable_falls_back_to_phase1_list(monkeypatch):
    fake = FakeBQ({"basket_members": RuntimeError("permission denied"), "universe_members": UNIVERSE})
    monkeypatch.setattr(ex.bigquery, "Client", lambda **k: fake)
    assert len(ex.load_tickers(date(2026, 11, 16), date(2026, 11, 20))) == 30


def _frame(n=3):
    return pd.DataFrame({"trade_date": pd.date_range("2026-11-10", periods=n), "open": 1.0,
                         "high": 1.0, "low": 1.0, "close": 1.0, "adj_close": 1.0,
                         "volume": 100, "source": "yfinance"})[ex.PRICE_COLS]


def test_fetch_uses_tiingo_for_misses_and_caps_calls(monkeypatch):
    tickers = [f"T{i}" for i in range(100)]
    monkeypatch.setattr(ex, "fetch_yfinance", lambda ts, s, e: {t: _frame() for t in ts[:50]})
    calls = []
    monkeypatch.setattr(ex, "fetch_tiingo",
                        lambda t, s, e: calls.append(t) or _frame().assign(source="tiingo"))
    df = ex.fetch(date(2026, 11, 10), date(2026, 11, 12), "run1", tickers=tickers)
    assert len(calls) == ex.TIINGO_MAX                      # 50 missing, only 40 tried
    assert df["ticker"].nunique() == 50 + ex.TIINGO_MAX
    assert list(df.columns) == ex.COLS


def test_fetch_yfinance_calls_in_chunks(monkeypatch):
    sizes = []
    monkeypatch.setattr(ex.yf, "download", lambda chunk, **k: sizes.append(len(chunk)) or pd.DataFrame())
    ex.fetch_yfinance([f"T{i}" for i in range(120)], date(2026, 11, 10), date(2026, 11, 12))
    assert sizes == [50, 50, 20]


def test_group_name_is_stable_and_set_specific():
    assert ex.group_name(["B", "A"]) == ex.group_name(["A", "B", "A"])
    assert ex.group_name(["A", "B"]) != ex.group_name(["A"])


def test_delete_is_scoped_to_loaded_tickers(monkeypatch):
    fake = FakeBQ({})
    fake.create_table = lambda *a, **k: None
    fake.load_table_from_uri = lambda *a, **k: SimpleNamespace(result=lambda: None)
    monkeypatch.setattr(ex.bigquery, "Client", lambda **k: fake)
    ex.to_bigquery(["gs://b/x.parquet"], [date(2026, 11, 16)], ["PLTR"], table_id="p.d.t")
    sql, cfg = fake.queries[0]
    assert "AND ticker IN UNNEST(@tickers)" in sql
    params = {p.name: p.values for p in cfg.query_parameters}
    assert params["tickers"] == ["PLTR"]
