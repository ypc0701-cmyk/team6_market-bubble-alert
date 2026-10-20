"""UI checks with warehouse-shaped rows; no GCP account or signal calculation."""

from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
import streamlit as st
from google.cloud import bigquery
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "dashboard" / "app.py"


@pytest.fixture
def run_app(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "market-bubble-alert")
    monkeypatch.setenv("BQ_DATASET", "marts_dev")
    signal_frame = pd.read_csv(ROOT / "docs/dummy_rows/daily_signals.csv")
    signal_frame["trade_date"] = pd.to_datetime(signal_frame["trade_date"]).dt.date
    signal_frame["computed_at"] = pd.Timestamp.now(tz="UTC")
    member_frame = pd.read_csv(ROOT / "docs/dummy_rows/daily_drawdowns.csv")
    member_frame = member_frame.loc[
        (member_frame["trade_date"] == "2026-10-07")
        & member_frame["basket"].isin(["speculative", "megacap"])
    ].copy()
    member_frame["company_name"] = member_frame["ticker"]

    def run(signal_rows=None, member_rows=None, fail=None, dataset="marts_dev"):
        st.cache_data.clear()
        monkeypatch.setenv("BQ_DATASET", dataset)
        signals = signal_frame.copy() if signal_rows is None else signal_rows
        members = member_frame.copy() if member_rows is None else member_rows
        calls = []

        def query(sql, **kwargs):
            calls.append((sql, kwargs))
            is_signal = "daily_signals" in sql
            if fail == "signals" or (fail == "members" and not is_signal):
                raise RuntimeError("Warehouse unavailable")
            rows = signals if is_signal else members
            return Mock(result=Mock(return_value=rows.to_dict("records")))

        monkeypatch.setattr(bigquery, "Client", Mock(return_value=Mock(query=query)))
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        return app, calls

    run.signals = signal_frame
    run.members = member_frame
    return run


@pytest.mark.parametrize("level,label", enumerate([
    "CALM", "STRAIN", "DIVERGENCE", "TOPPING", "REPRICING", "WASHOUT"
]))
def test_renders_warehouse_verdict_for_each_level(run_app, level, label):
    rows = run_app.signals.copy()
    rows.loc[rows.index[-1], ["dial_level", "dial_label", "dial_explanation"]] = [level, label, "Warehouse explanation."]
    app, _ = run_app(signal_rows=rows)
    assert not app.exception
    assert not app.error
    assert app.metric[0].value == f"{level} / 5"
    assert "Warehouse explanation." in [item.value for item in app.info]
    assert len(app.get("vega_lite_chart")) == 3


@pytest.mark.parametrize("badge", ["off_pattern", "credit_only"])
def test_unarmed_badges_and_roster_events(run_app, badge):
    rows = run_app.signals.copy()
    rows["badge"] = badge
    rows["armed_since"] = None
    rows["is_armed"] = False
    rows["roster_changed_today"] = True
    rows["armed_state_change"] = "disarmed_quiet"
    app, _ = run_app(signal_rows=rows)
    assert not app.exception
    assert app.metric[2].value == "Not armed"
    assert any("Pattern qualifier:" in item.value for item in app.caption)
    assert "Roster changed" in app.dataframe[0].value.iloc[0]["Event"]


def test_member_query_uses_verdict_date_and_missing_values_stay_missing(run_app):
    members = run_app.members.copy()
    members["is_broken"] = members["is_broken"].astype(object)
    members.loc[members["ticker"] == "CRWV", ["drawdown", "return_6m", "is_broken"]] = None
    app, calls = run_app(member_rows=members)
    assert not app.exception
    assert not app.error
    params = calls[1][1]["job_config"].query_parameters
    assert params[0].value == run_app.signals["trade_date"].max()
    table = app.dataframe[0].value
    assert table.iloc[-1]["ticker"] == "CRWV"
    assert pd.isna(table.iloc[-1]["drawdown"])
    assert table.iloc[-1]["is_broken"] == "Not available"
    assert table["drawdown"].dropna().is_monotonic_increasing


def test_empty_signals_show_no_verdict(run_app):
    app, calls = run_app(signal_rows=pd.DataFrame())
    assert not app.exception
    assert not app.metric
    assert len(calls) == 1
    assert any("No signal rows" in item.value for item in app.info)


def test_signal_query_failure_shows_no_verdict(run_app):
    app, _ = run_app(fail="signals")
    assert not app.exception
    assert not app.metric
    assert any("could not be loaded" in item.value for item in app.error)


def test_member_failure_is_visible_and_does_not_hide_verdict(run_app):
    app, _ = run_app(fail="members")
    assert not app.exception
    assert len(app.metric) == 4
    assert any("Member data could not be loaded" in item.value for item in app.error)


def test_old_calculations_and_basket_audit_are_flagged(run_app):
    rows = run_app.signals.copy()
    rows["computed_at"] = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=100)
    rows["basket_audit_flag"] = True
    app, _ = run_app(signal_rows=rows)
    assert not app.exception
    assert any("72 hours" in item.value for item in app.warning)
    assert any("Basket audit" in item.value for item in app.warning)


def test_production_uses_only_production_tables(run_app):
    app, calls = run_app(dataset="marts")
    assert not app.exception
    assert not app.error
    assert len(calls) == 2
    assert all("market-bubble-alert.marts." in sql for sql, _ in calls)
    assert all("marts_dev" not in sql for sql, _ in calls)


def test_invalid_dataset_is_rejected_before_query(run_app):
    app, calls = run_app(dataset="raw")
    assert not app.exception
    assert not calls
    assert any("Choose marts_dev" in item.value for item in app.error)
