import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    import main
    importlib.reload(main)
    return TestClient(main.app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["data_source"] == "dummy"
    assert r.json()["scored_tickers"] == 20


def test_risk_known_ticker(client):
    body = client.get("/risk", params={"ticker": "NVDA"}).json()
    assert body["ticker"] == "NVDA"
    assert 0 <= body["prob_drop_20pct_60d"] <= 1
    assert body["in_our_basket"] is False
    assert body["data_source"] == "dummy"
    assert set(body) >= {"as_of", "rank_in_universe", "model_version", "dial_level"}


def test_risk_is_case_insensitive(client):
    assert client.get("/risk", params={"ticker": "crwv"}).json()["in_our_basket"] is True


def test_risk_unknown_ticker_404(client):
    assert client.get("/risk", params={"ticker": "ZZZZ"}).status_code == 404


def test_risk_bad_input_422(client):
    assert client.get("/risk", params={"ticker": "NVDA; DROP"}).status_code == 422
    assert client.get("/risk").status_code == 422


def test_basket_has_our_11_sorted(client):
    body = client.get("/basket").json()
    tickers = [s["ticker"] for s in body["stocks"]]
    assert len(tickers) == 11 and body["missing_from_scores"] == []
    probs = [s["prob_drop_20pct_60d"] for s in body["stocks"]]
    assert probs == sorted(probs, reverse=True)
    assert 0 <= body["universe_median_prob"] <= 1


def test_bigquery_mode_uses_bigquery_loader(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "bigquery")
    import main
    importlib.reload(main)
    fake = ({"NVDA": {"ticker": "NVDA", "as_of": "2026-11-20", "prob_drop_20pct_60d": 0.2,
                      "rank_in_universe": 5, "model_version": "v1"}},
            {"as_of": "2026-11-20", "dial_level": 1, "dial_label": "STRAIN"})
    monkeypatch.setitem(main.LOADERS, "bigquery", lambda: fake)
    body = TestClient(main.app).get("/risk", params={"ticker": "NVDA"}).json()
    assert body["data_source"] == "bigquery" and body["model_version"] == "v1"
    assert body["dial_label"] == "STRAIN"
