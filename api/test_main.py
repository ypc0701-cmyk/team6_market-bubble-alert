import datetime as dt
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    import main
    importlib.reload(main)
    return TestClient(main.app)


def test_health_serves_latest_week_only(client):
    body = client.get("/health").json()
    assert body["data_source"] == "dummy"
    assert body["as_of"] == "2026-11-13"
    assert body["scored_tickers"] == 19


def test_risk_has_all_contract_columns(client):
    import main
    body = client.get("/risk", params={"ticker": "NVDA"}).json()
    assert set(main.SCORE_COLUMNS) <= set(body)
    assert body["role"] == "universe" and body["in_our_basket"] is False
    assert 0 <= body["prob_drop_20pct_60d"] <= 1
    assert isinstance(body["universe_size"], int)
    assert body["data_source"] == "dummy"


def test_risk_is_case_insensitive_and_uses_role(client):
    body = client.get("/risk", params={"ticker": "crwv"}).json()
    assert body["role"] == "our_basket" and body["in_our_basket"] is True


def test_risk_unknown_ticker_404(client):
    assert client.get("/risk", params={"ticker": "ZZZZ"}).status_code == 404


def test_risk_bad_input_422(client):
    assert client.get("/risk", params={"ticker": "NVDA; DROP"}).status_code == 422
    assert client.get("/risk").status_code == 422


def test_basket_uses_role_and_reports_missing(client):
    body = client.get("/basket").json()
    assert {s["role"] for s in body["stocks"]} == {"our_basket"}
    assert len(body["stocks"]) == 10
    assert body["missing_from_scores"] == ["SPCX"]  # under 126 trading days of history
    probs = [s["prob_drop_20pct_60d"] for s in body["stocks"]]
    assert probs == sorted(probs, reverse=True)
    assert body["model_version"] and body["trained_at"] and body["universe_size"] == 9
    assert 0 <= body["universe_median_prob"] <= 1


def test_prob_change_null_on_first_week():
    import main
    row = main._clean({"ticker": "X", "as_of": dt.date(2026, 11, 20), "prob_drop_20pct_60d": 0.3,
                       "rank_in_universe": 2, "model_version": "v1",
                       "trained_at": dt.datetime(2026, 11, 20, 23, 0, tzinfo=dt.timezone.utc),
                       "model_name": "logistic", "role": "universe", "universe_size": 120,
                       "pct_rank_in_universe": 0.0167, "prob_change_1w": None,
                       "scored_at": dt.datetime(2026, 11, 21, 2, 0, tzinfo=dt.timezone.utc)})
    assert row["prob_change_1w"] is None
    assert row["as_of"] == "2026-11-20" and row["trained_at"].startswith("2026-11-20T23:00")


def test_bigquery_mode_uses_bigquery_loader(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "bigquery")
    import main
    importlib.reload(main)
    nvda = {"ticker": "NVDA", "as_of": "2026-11-20", "prob_drop_20pct_60d": 0.2,
            "rank_in_universe": 5, "model_version": "v1", "trained_at": "2026-11-20T23:00:00+00:00",
            "model_name": "boosted_tree", "role": "universe", "universe_size": 120,
            "pct_rank_in_universe": 0.0417, "prob_change_1w": -0.01,
            "scored_at": "2026-11-21T02:00:00+00:00"}
    fake = ({"NVDA": nvda}, ["CRWV"], {"as_of": "2026-11-20", "dial_level": 1, "dial_label": "STRAIN"})
    monkeypatch.setitem(main.LOADERS, "bigquery", lambda: fake)
    c = TestClient(main.app)
    body = c.get("/risk", params={"ticker": "NVDA"}).json()
    assert body["data_source"] == "bigquery" and body["model_version"] == "v1"
    assert body["dial_label"] == "STRAIN"
    assert c.get("/basket").json()["missing_from_scores"] == ["CRWV"]
