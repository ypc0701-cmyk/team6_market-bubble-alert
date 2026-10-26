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


def table_with(app, *columns):
    matches = [item.value for item in app.dataframe if set(columns).issubset(item.value.columns)]
    assert len(matches) == 1, f"Expected one table with columns {columns}"
    return matches[0]


@pytest.fixture
def run_app(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "market-bubble-alert")
    monkeypatch.setenv("BQ_DATASET", "marts_dev")
    signal_frame = pd.read_csv(ROOT / "docs/dummy_rows/daily_signals.csv")
    signal_frame["trade_date"] = pd.to_datetime(signal_frame["trade_date"]).dt.date
    signal_frame["computed_at"] = pd.Timestamp.now(tz="UTC")
    member_frame = pd.read_csv(ROOT / "docs/dummy_rows/daily_drawdowns.csv")
    member_frame = member_frame.loc[
        member_frame["trade_date"] == "2026-10-07"
    ].copy()
    member_frame["company_name"] = member_frame["ticker"]
    episode_frame = pd.read_csv(ROOT / "docs/dummy_rows/episodes.csv")
    episode_frame["computed_at"] = pd.Timestamp.now(tz="UTC")

    def run(signal_rows=None, member_rows=None, episode_rows=None, fail=None, dataset="marts_dev"):
        st.cache_data.clear()
        monkeypatch.setenv("BQ_DATASET", dataset)
        signals = signal_frame.copy() if signal_rows is None else signal_rows
        members = member_frame.copy() if member_rows is None else member_rows
        episodes = episode_frame.copy() if episode_rows is None else episode_rows
        calls = []

        def query(sql, **kwargs):
            calls.append((sql, kwargs))
            kind = "signals" if "daily_signals" in sql else ("episodes" if ".episodes`" in sql else "members")
            if fail == kind:
                raise RuntimeError("Warehouse unavailable")
            rows = {"signals": signals, "members": members, "episodes": episodes}[kind]
            return Mock(result=Mock(return_value=rows.to_dict("records")))

        monkeypatch.setattr(bigquery, "Client", Mock(return_value=Mock(query=query)))
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        return app, calls

    run.signals = signal_frame
    run.members = member_frame
    run.episodes = episode_frame
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
    assert len(app.get("vega_lite_chart")) == 5


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
    assert "Roster changed" in table_with(app, "Event").iloc[0]["Event"]


def test_member_query_uses_verdict_date_and_missing_values_stay_missing(run_app):
    members = run_app.members.copy()
    members["is_broken"] = members["is_broken"].astype(object)
    members.loc[members["ticker"] == "CRWV", ["drawdown", "return_6m", "is_broken"]] = None
    app, calls = run_app(member_rows=members)
    assert not app.exception
    assert not app.error
    params = calls[1][1]["job_config"].query_parameters
    assert params[0].value == run_app.signals["trade_date"].max()
    table = table_with(app, "ticker", "drawdown")
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
    assert app.metric[0].label == "Dial level"
    assert table_with(app, "Confirmed", "start_date").shape[0] > 0
    assert any("Member data could not be loaded" in item.value for item in app.error)


def test_old_calculations_and_basket_audit_are_flagged(run_app):
    rows = run_app.signals.copy()
    rows["computed_at"] = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=100)
    rows["basket_audit_flag"] = True
    app, _ = run_app(signal_rows=rows)
    assert not app.exception
    assert any("72 hours" in item.value for item in app.warning)
    assert any("AI-specific:" in item.value for item in app.info)


def test_production_uses_only_production_tables(run_app):
    app, calls = run_app(dataset="marts")
    assert not app.exception
    assert not app.error
    assert len(calls) == 3
    assert all("market-bubble-alert.marts." in sql for sql, _ in calls)
    assert all("marts_dev" not in sql for sql, _ in calls)


def test_invalid_dataset_is_rejected_before_query(run_app):
    app, calls = run_app(dataset="raw")
    assert not app.exception
    assert not calls
    assert any("Choose marts_dev" in item.value for item in app.error)


def test_evidence_and_comparison_use_warehouse_values(run_app):
    rows = run_app.signals.copy()
    rows.loc[rows.index[-1], ["breadth", "spec_median_drawdown", "mega_median_drawdown", "credit_distance"]] = [0.12345, -0.321, -0.11, -0.0123]
    app, _ = run_app(signal_rows=rows)
    assert not app.exception
    assert not app.error
    metrics = {item.label: item.value for item in app.metric}
    assert metrics["Speculative breadth"] == "12.3%"
    assert metrics["Speculative median drawdown"] == "-32.1%"
    assert metrics["Credit ratio distance"] == "-1.2%"
    comparison = table_with(app, "Group").set_index("Group")
    assert comparison.loc["Megacap median", "drawdown"] == pytest.approx(-11.0)
    assert pd.isna(comparison.loc["ARKK reference ETF", "Eligible members"])


def test_conditions_are_displayed_without_recomputing_them(run_app):
    rows = run_app.signals.copy()
    rows.loc[rows.index[-1], "breadth"] = 0.0
    rows.loc[rows.index[-1], "cond_divergence"] = True
    rows.loc[rows.index[-1], "cond_repricing"] = False
    app, _ = run_app(signal_rows=rows)
    table = table_with(app, "Condition").set_index("Condition")
    assert table.loc["Divergence", "Today"] == "Met"
    assert table.loc["Repricing", "Today"] == "Not met"


def test_missing_context_values_are_not_zero(run_app):
    rows = run_app.signals.copy()
    for column in ["breadth", "spec_median_drawdown", "mega_median_drawdown", "spx_distance", "credit_distance", "concentration_distance", "arkk_drawdown"]:
        rows[column] = None
    rows["cond_divergence"] = None
    app, _ = run_app(signal_rows=rows)
    assert not app.exception
    assert not app.error
    metrics = {item.label: item.value for item in app.metric}
    assert metrics["Speculative breadth"] == "N/A"
    assert metrics["Credit ratio distance"] == "N/A"
    assert table_with(app, "Group")["drawdown"].isna().all()
    assert table_with(app, "Condition").iloc[0]["Today"] == "Not available"
    assert any("Credit and concentration history is not available" in item.value for item in app.info)


def test_episode_query_uses_verdict_date_and_keeps_unconfirmed_dates_empty(run_app):
    rows = run_app.episodes.copy()
    latest_index = rows["start_date"].idxmax()
    rows.loc[latest_index, "is_held"] = False
    rows.loc[latest_index, ["held_date", "end_date", "disarm_date"]] = None
    app, calls = run_app(episode_rows=rows)
    assert not app.exception
    assert not app.error
    episode_call = next(call for call in calls if ".episodes`" in call[0])
    assert episode_call[1]["job_config"].query_parameters[0].value == run_app.signals["trade_date"].max()
    table = table_with(app, "Confirmed", "start_date")
    assert table.iloc[0]["Confirmed"] == "No"
    assert pd.isna(table.iloc[0]["held_date"])
    assert pd.isna(table.iloc[0]["end_date"])


def test_empty_episode_history_is_visible_without_hiding_the_dashboard(run_app):
    app, _ = run_app(episode_rows=pd.DataFrame())
    assert not app.exception
    assert not app.error
    assert app.metric[0].label == "Dial level"
    assert any("No divergence episodes" in item.value for item in app.info)


def test_episode_failure_does_not_hide_verdict_or_members(run_app):
    app, _ = run_app(fail="episodes")
    assert not app.exception
    assert app.metric[0].label == "Dial level"
    assert not table_with(app, "ticker", "drawdown").empty
    assert any("Episode history could not be loaded" in item.value for item in app.error)


def test_member_switch_keeps_global_speculative_verdict(run_app):
    app, _ = run_app()
    before = app.metric[3].value
    app.sidebar.selectbox[1].set_value("megacap").run()
    assert not app.exception
    assert not app.error
    assert app.metric[3].label == "Speculative broken / eligible"
    assert app.metric[3].value == before
    expected = set(run_app.members.loc[run_app.members["basket"] == "megacap", "ticker"])
    assert set(table_with(app, "ticker", "drawdown")["ticker"]) == expected


def test_refresh_clears_episode_cache_with_other_marts(run_app):
    app, calls = run_app()
    assert len(calls) == 3
    app.button[0].click().run()
    assert not app.exception
    assert not app.error
    assert len(calls) == 6
    assert sum(".episodes`" in sql for sql, _ in calls) == 2



@pytest.mark.parametrize("ticker", ["CRWV", "ARKK", "^GSPC"])
def test_audit_qualifier_keeps_warning_when_any_active_price_is_missing(run_app, ticker):
    rows = run_app.signals.copy()
    rows["basket_audit_flag"] = True
    members = run_app.members.copy()
    members.loc[members["ticker"] == ticker, "adj_close"] = None
    app, _ = run_app(signal_rows=rows, member_rows=members)
    assert not app.exception
    assert not any("AI-specific:" in item.value for item in app.info)
    assert any("Price coverage is incomplete" in item.value for item in app.warning)
    assert app.metric[0].value == f"{int(rows.iloc[-1]['dial_level'])} / 5"


def test_young_listing_with_a_price_does_not_block_ai_specific_qualifier(run_app):
    rows = run_app.signals.copy()
    rows["basket_audit_flag"] = True
    members = run_app.members.copy()
    members.loc[members["ticker"] == "CRWV", ["drawdown", "return_6m"]] = None
    members.loc[members["ticker"] == "CRWV", "is_signal_eligible"] = False
    app, _ = run_app(signal_rows=rows, member_rows=members)
    assert not app.exception
    assert any("AI-specific: the broader speculative market (ARKK) does not confirm this break." == item.value for item in app.info)
    assert not any("Basket audit:" in item.value for item in app.warning)


@pytest.mark.parametrize("fail,empty", [("members", False), (None, True)])
def test_unverified_price_coverage_never_claims_ai_specific(run_app, fail, empty):
    rows = run_app.signals.copy()
    rows["basket_audit_flag"] = True
    members = pd.DataFrame() if empty else None
    app, _ = run_app(signal_rows=rows, member_rows=members, fail=fail)
    assert not app.exception
    assert not any("AI-specific:" in item.value for item in app.info)
    assert any("Basket audit:" in item.value for item in app.warning)
    assert app.metric[0].value == f"{int(rows.iloc[-1]['dial_level'])} / 5"
