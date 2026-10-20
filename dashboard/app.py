"""Display the signal marts. Signal calculations stay in dbt."""

import logging
import os
import re

import altair as alt
import pandas as pd
import streamlit as st
from google.cloud import bigquery


LOGGER = logging.getLogger(__name__)
PROJECT = os.getenv("GCP_PROJECT", "market-bubble-alert")
DATASET = os.getenv("BQ_DATASET", "marts_dev")
LOCATION = os.getenv("BQ_LOCATION", "US")
BADGE_LABELS = {"off_pattern": "Off pattern", "credit_only": "Credit only"}

st.set_page_config(page_title="Market Bubble Alert", layout="wide")
st.title("Market Bubble Alert")
st.caption("Daily market-pattern monitoring for the selected AI stock basket.")

if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", PROJECT):
    st.error("The Google Cloud project setting is invalid.")
    st.stop()
if DATASET not in {"marts_dev", "marts"}:
    st.error("Choose marts_dev for development or marts for production.")
    st.stop()

st.sidebar.write("Production data" if DATASET == "marts" else "Development data")
st.sidebar.caption(f"{PROJECT}.{DATASET}")
history_days = st.sidebar.selectbox("History", [90, 180, 365, "All"], index=2)
basket = st.sidebar.selectbox("Members", ["speculative", "megacap"])
st.sidebar.caption("The open page checks for updates every 60 seconds.")


def query_frame(project, location, sql, parameters=None):
    client = bigquery.Client(project=project)
    config = bigquery.QueryJobConfig(
        maximum_bytes_billed=1_000_000_000,
        query_parameters=parameters or [],
    )
    try:
        rows = client.query(sql, location=location, job_config=config).result(timeout=60)
        return pd.DataFrame([dict(row.items()) for row in rows])
    finally:
        client.close()


@st.cache_data(ttl=60)
def load_signals(project, dataset, location):
    # These settings are cache keys as well as validated SQL identifiers.
    return query_frame(project, location, f"""
        SELECT trade_date, dial_level, dial_label, dial_explanation,
               badge, is_armed, armed_since, armed_state_change,
               credit_status, spec_members_broken, spec_members_valid,
               breadth, spx_distance, spec_median_drawdown, arkk_drawdown,
               basket_audit_flag, roster_changed_today, computed_at
        FROM `{project}.{dataset}.daily_signals`
        ORDER BY trade_date
    """)


@st.cache_data(ttl=60)
def load_members(project, dataset, location, as_of):
    # Start with the active roster so a missing price remains a visible N/A row.
    return query_frame(project, location, f"""
        SELECT m.ticker, m.company_name, m.basket,
               d.drawdown, d.return_6m, d.is_broken,
               d.is_signal_eligible, d.computed_at
        FROM `{project}.{dataset}.basket_members` AS m
        LEFT JOIN `{project}.{dataset}.daily_drawdowns` AS d
          ON m.ticker = d.ticker AND m.basket = d.basket
         AND d.trade_date = @as_of
        WHERE m.basket IN ('speculative', 'megacap')
          AND m.added_date <= @as_of
          AND (m.removed_date IS NULL OR @as_of < m.removed_date)
          AND m.listing_date <= @as_of
        ORDER BY d.drawdown ASC NULLS LAST, m.ticker
    """, [bigquery.ScalarQueryParameter("as_of", "DATE", as_of)])


def text(value, default="Not available"):
    return default if pd.isna(value) else str(value)


def count(value):
    return "N/A" if pd.isna(value) else str(int(value))


def show_freshness(latest):
    now = pd.Timestamp.now(tz="UTC")
    computed = pd.to_datetime(latest["computed_at"], utc=True, errors="coerce")
    st.caption(f"Data as of: {latest['trade_date']:%Y-%m-%d}")
    st.caption(
        "Calculated at: "
        + ("Not available" if pd.isna(computed) else computed.strftime("%Y-%m-%d %H:%M UTC"))
        + f" · Last checked: {now:%Y-%m-%d %H:%M UTC}"
    )
    if pd.isna(computed):
        st.warning("The calculation time is unavailable; freshness could not be verified.")
    elif now - computed > pd.Timedelta(hours=72):
        st.warning("These results were calculated more than 72 hours ago. Check the pipeline before using them.")

    # A conservative display warning, not an exchange-calendar or DAG health check.
    local_now = now.tz_convert("America/New_York")
    expected_day = local_now.normalize().tz_localize(None)
    if local_now.hour < 19:
        expected_day -= pd.Timedelta(days=1)
    lag_days = len(pd.bdate_range(latest["trade_date"] + pd.Timedelta(days=1), expected_day))
    if lag_days >= 2:
        st.warning(
            "The signal date is at least two weekdays behind the expected evening update. "
            "Check upstream data; market holidays and provider delays can also cause this warning."
        )


def event_rows(history):
    events = history.loc[
        history["roster_changed_today"].fillna(False)
        | history["armed_state_change"].notna(),
        ["trade_date", "roster_changed_today", "armed_state_change"],
    ].copy()
    if events.empty:
        events["Event"] = pd.Series(dtype="str")
    else:
        events["Event"] = events.apply(
            lambda row: "; ".join(
                (["Roster changed"] if pd.notna(row["roster_changed_today"]) and bool(row["roster_changed_today"]) else [])
                + ([str(row["armed_state_change"])] if pd.notna(row["armed_state_change"]) else [])
            ), axis=1,
        )
    return events


def show_history(history):
    st.subheader("Breadth vs. S&P distance from high")
    st.caption("Orange: breadth (left axis). Blue: S&P below high (right axis). Both show percentages on different scales.")
    base = alt.Chart(history).encode(x=alt.X("trade_date:T", title="Trading date"))
    breadth_chart = base.mark_line(color="#d97706").encode(
        y=alt.Y("breadth:Q", title="Broken share", axis=alt.Axis(format=".0%"), scale=alt.Scale(domain=[0, 1])),
        tooltip=[alt.Tooltip("trade_date:T", title="Date"), alt.Tooltip("breadth:Q", format=".1%", title="Breadth")],
    )
    spx_chart = base.mark_line(color="#2563eb").encode(
        y=alt.Y("spx_distance:Q", title="S&P below high", axis=alt.Axis(format=".0%", orient="right")),
        tooltip=[alt.Tooltip("trade_date:T", title="Date"), alt.Tooltip("spx_distance:Q", format=".1%", title="S&P distance")],
    )
    st.altair_chart(
        alt.layer(breadth_chart, spx_chart).resolve_scale(y="independent").properties(height=280),
        width="stretch",
    )

    st.subheader("Dial history")
    dial = base.mark_line(interpolate="step-after", color="#7c3aed").encode(
        y=alt.Y("dial_level:Q", title="Dial level", scale=alt.Scale(domain=[0, 5]), axis=alt.Axis(values=list(range(6)))),
        tooltip=["trade_date:T", "dial_level:Q", "dial_label:N", "badge:N"],
    )
    events = event_rows(history)
    rules = alt.Chart(events).mark_rule(color="#64748b", strokeDash=[4, 3]).encode(
        x="trade_date:T", tooltip=["trade_date:T", "Event:N"],
    )
    st.altair_chart((dial + rules).properties(height=200), width="stretch")
    if not events.empty:
        with st.expander("Arming and roster events"):
            st.dataframe(events[["trade_date", "Event"]], hide_index=True, width="stretch")


def show_members(members, as_of):
    selected = members.loc[members["basket"] == basket].copy()
    st.subheader(f"Member drawdowns · {basket}")
    st.caption(f"Same trading date as the verdict: {as_of:%Y-%m-%d}. More negative means farther below the reference high.")
    if selected.empty:
        st.info("No members are available for this basket and trading date.")
        return
    selected = selected.sort_values("drawdown", na_position="last")
    drawable = selected.loc[selected["drawdown"].notna()]
    if not drawable.empty:
        chart = alt.Chart(drawable).mark_bar().encode(
            x=alt.X("drawdown:Q", title="Drawdown", axis=alt.Axis(format=".0%")),
            y=alt.Y("ticker:N", sort=selected["ticker"].tolist(), title=None),
            color=alt.Color("is_broken:N", title="Broken", scale=alt.Scale(domain=[True, False], range=["#dc2626", "#64748b"])),
            tooltip=["ticker:N", "company_name:N", alt.Tooltip("drawdown:Q", format=".1%"), "is_signal_eligible:N"],
        ).properties(height=max(220, len(drawable) * 24))
        st.altair_chart(chart, width="stretch")
    if selected["drawdown"].isna().any():
        st.warning("Some members have no usable drawdown. Their table values remain unavailable.")

    # Percentage conversion is formatting only; both measures come from dbt.
    table = selected[["ticker", "company_name", "drawdown", "return_6m", "is_broken", "is_signal_eligible"]].copy()
    for column in ["drawdown", "return_6m"]:
        table[column] = pd.to_numeric(table[column], errors="coerce") * 100
    for column in ["is_broken", "is_signal_eligible"]:
        table[column] = table[column].map(lambda value: "Not available" if pd.isna(value) else ("Yes" if value else "No"))
    st.dataframe(
        table, hide_index=True, width="stretch",
        column_config={
            "ticker": "Ticker", "company_name": "Company",
            "drawdown": st.column_config.NumberColumn("Drawdown", format="%.1f%%"),
            "return_6m": st.column_config.NumberColumn("6-month return", format="%.1f%%"),
            "is_broken": "Broken", "is_signal_eligible": "Signal eligible",
        },
    )
    st.caption("A missing six-month return can reflect a young listing. Missing values are not zero returns.")


@st.fragment(run_every=60)
def dashboard():
    if st.button("Refresh data"):
        load_signals.clear()
        load_members.clear()
    try:
        signals = load_signals(PROJECT, DATASET, LOCATION)
    except Exception:
        LOGGER.exception("Could not load daily_signals")
        st.error("Signal data could not be loaded. Ask the pipeline owner to check the selected dataset and access.")
        return
    if signals.empty:
        st.info("No signal rows are available yet. The pipeline needs to build the selected marts.")
        return
    signals["trade_date"] = pd.to_datetime(signals["trade_date"])
    signals = signals.sort_values("trade_date")
    latest = signals.iloc[-1]
    as_of = latest["trade_date"].date()
    show_freshness(latest)

    cards = st.columns(4)
    cards[0].metric("Dial level", f"{count(latest['dial_level'])} / 5")
    cards[0].caption(text(latest["dial_label"]))
    cards[1].metric("Credit status", text(latest["credit_status"]))
    armed = latest["is_armed"]
    armed_since = "Not armed" if pd.notna(armed) and not bool(armed) else text(latest["armed_since"])
    cards[2].metric("Armed since", armed_since)
    cards[3].metric("Broken / eligible names", f"{count(latest['spec_members_broken'])} / {count(latest['spec_members_valid'])}")
    st.info(text(latest["dial_explanation"]))
    badge = latest["badge"]
    if pd.notna(badge):
        st.caption("Pattern qualifier: " + BADGE_LABELS.get(badge, str(badge)))
    if pd.notna(latest["basket_audit_flag"]) and bool(latest["basket_audit_flag"]):
        st.warning(
            "Basket audit: the selected AI basket differs materially from ARKK. "
            "Review basket construction before using this reading as a market-wide signal."
        )

    history = signals if history_days == "All" else signals.loc[
        signals["trade_date"] >= latest["trade_date"] - pd.Timedelta(days=history_days)
    ]
    show_history(history)
    try:
        members = load_members(PROJECT, DATASET, LOCATION, as_of)
        if members.empty:
            st.info("No member data are available for the verdict date.")
        else:
            show_members(members, as_of)
    except Exception:
        LOGGER.exception("Could not load member drawdowns")
        st.error("Member data could not be loaded for the verdict date. The verdict above is from daily_signals.")

    with st.expander("Recent readings"):
        st.dataframe(signals[["trade_date", "dial_level", "dial_label", "credit_status"]].tail(10), hide_index=True)
    st.subheader("How to read this")
    st.write(
        "Start with the dial and its explanation. Levels run from 0 CALM through 1 STRAIN, "
        "2 DIVERGENCE, 3 TOPPING, 4 REPRICING, and 5 WASHOUT. Breadth measures how many "
        "eligible speculative names are at least 25% below their reference highs. Compare it "
        "with the S&P's distance from its high, then inspect member drawdowns and credit status. "
        "Badges qualify unusual patterns; an audit warning calls for checking the selected basket. "
        "N/A means unavailable, and a historical reading describes its displayed date."
    )


dashboard()
