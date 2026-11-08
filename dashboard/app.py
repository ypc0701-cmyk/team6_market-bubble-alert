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
history_days = st.sidebar.selectbox(
    "History", [90, 180, 365, "All"], index=2,
    format_func=lambda value: "All history" if value == "All" else f"{value} calendar days",
)
basket = st.sidebar.selectbox("Members", ["speculative", "megacap"])
st.sidebar.caption("History changes the trend charts. Members changes the member view. The verdict always shows the latest signal.")
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
               spec_members_in_force, mega_members_valid, mega_median_drawdown,
               credit_distance, concentration_distance, is_concentration_broken,
               cond_divergence, cond_divergence_strict, cond_deterioration,
               cond_repricing, cond_washout, divergence_run_days,
               quiet_days_used, armed_ceiling_date,
               basket_audit_flag, roster_changed_today, computed_at
        FROM `{project}.{dataset}.daily_signals`
        ORDER BY trade_date
    """)


@st.cache_data(ttl=60)
def load_members(project, dataset, location, as_of):
    # Load every active, listed symbol so the qualifier checks price coverage.
    # show_members filters this result to the selected basket for display.
    return query_frame(project, location, f"""
        SELECT m.ticker, m.company_name, m.basket,
               d.adj_close, d.drawdown, d.return_6m, d.is_broken,
               d.is_signal_eligible, d.computed_at
        FROM `{project}.{dataset}.basket_members` AS m
        LEFT JOIN `{project}.{dataset}.daily_drawdowns` AS d
          ON m.ticker = d.ticker AND m.basket = d.basket
         AND d.trade_date = @as_of
        WHERE m.added_date <= @as_of
          AND (m.removed_date IS NULL OR @as_of < m.removed_date)
          AND m.listing_date <= @as_of
        ORDER BY d.drawdown ASC NULLS LAST, m.ticker
    """, [bigquery.ScalarQueryParameter("as_of", "DATE", as_of)])


@st.cache_data(ttl=60)
def load_episodes(project, dataset, location, as_of):
    return query_frame(project, location, f"""
        SELECT episode_id, start_date, end_date, is_open, trading_days,
               max_divergence_run, is_held, held_date, max_breadth,
               min_spec_median_drawdown, disarm_date, disarm_reason, computed_at
        FROM `{project}.{dataset}.episodes`
        WHERE start_date <= @as_of
        ORDER BY start_date DESC
    """, [bigquery.ScalarQueryParameter("as_of", "DATE", as_of)])


def text(value, default="Not available"):
    return default if pd.isna(value) else str(value)


def count(value):
    return "N/A" if pd.isna(value) else str(int(value))


def percent(value):
    return "N/A" if pd.isna(value) else f"{value:.1%}"


def flag_text(value, yes="Met", no="Not met"):
    return "Not available" if pd.isna(value) else (yes if bool(value) else no)


def show_basket_qualifier(latest, members):
    if pd.isna(latest["basket_audit_flag"]) or not bool(latest["basket_audit_flag"]):
        return
    # Price availability is separate from IPO maturity and usable drawdowns.
    coverage_complete = (
        members is not None and not members.empty
        and members["adj_close"].notna().all()
    )
    if coverage_complete:
        st.info("AI-specific: the broader speculative market (ARKK) does not confirm this break.")
        st.caption("Qualifier applies to the AI tier only. The warehouse dial, badge and armed state are unchanged.")
    else:
        st.warning(
            "Basket audit: the selected AI basket differs materially from ARKK. "
            "Price coverage is incomplete or unavailable for the verdict date. "
            "Review the data and basket before using this reading."
        )


def show_evidence(latest):
    st.subheader("Signal evidence")
    metrics = st.columns(4)
    metrics[0].metric("Speculative breadth", percent(latest["breadth"]), help="Share of eligible speculative names at least 25% below their reference highs.")
    metrics[1].metric("Speculative median drawdown", percent(latest["spec_median_drawdown"]), help="Median drawdown among eligible speculative members.")
    metrics[2].metric("S&P distance from high", percent(latest["spx_distance"]), help="S&P 500 distance from its trailing 252-trading-day high. Negative means below the high.")
    metrics[3].metric("Credit ratio distance", percent(latest["credit_distance"]), help="HYG / IEF distance from its trailing 126-trading-day high.")
    st.caption(
        f"Eligible speculative members: {count(latest['spec_members_valid'])} of {count(latest['spec_members_in_force'])}. "
        f"Current divergence run: {count(latest['divergence_run_days'])} trading days."
    )
    if pd.notna(latest["is_armed"]) and bool(latest["is_armed"]):
        ceiling = pd.to_datetime(latest["armed_ceiling_date"], errors="coerce")
        ceiling_text = "Not available" if pd.isna(ceiling) else ceiling.strftime("%Y-%m-%d")
        st.caption(f"Armed clock: {count(latest['quiet_days_used'])} of 378 quiet trading days used. Calendar ceiling: {ceiling_text}.")
    with st.expander("Today's conditions"):
        labels = {
            "cond_divergence": "Divergence",
            "cond_divergence_strict": "Strict divergence",
            "cond_deterioration": "Deterioration",
            "cond_repricing": "Repricing",
            "cond_washout": "Washout",
        }
        conditions = pd.DataFrame([
            {"Condition": label, "Today": flag_text(latest[column])}
            for column, label in labels.items()
        ])
        st.dataframe(conditions, hide_index=True, width="stretch", key="signal_conditions")
        st.caption("These conditions describe today. The verdict also depends on armed memory and the ordering of dial rules.")


def show_market_context(latest, history):
    st.subheader("Market context")
    comparison_tab, ratios_tab = st.tabs(["Basket comparison", "Credit and concentration"])
    with comparison_tab:
        comparison = pd.DataFrame({
            "Group": ["Speculative median", "Megacap median", "ARKK reference ETF"],
            "drawdown": [latest["spec_median_drawdown"], latest["mega_median_drawdown"], latest["arkk_drawdown"]],
            "Eligible members": [latest["spec_members_valid"], latest["mega_members_valid"], None],
        })
        drawable = comparison.dropna(subset=["drawdown"])
        if not drawable.empty:
            chart = alt.Chart(drawable).mark_bar().encode(
                x=alt.X("drawdown:Q", title="Drawdown", axis=alt.Axis(format=".0%")),
                y=alt.Y("Group:N", sort=comparison["Group"].tolist(), title=None),
                color=alt.Color("Group:N", legend=None, scale=alt.Scale(
                    domain=comparison["Group"].tolist(), range=["#d97706", "#2563eb", "#64748b"],
                )),
                tooltip=["Group:N", alt.Tooltip("drawdown:Q", format=".1%", title="Drawdown")],
            ).properties(height=180)
            st.altair_chart(chart, width="stretch")
        table = comparison.copy()
        table["drawdown"] = pd.to_numeric(table["drawdown"], errors="coerce") * 100
        st.dataframe(table, hide_index=True, width="stretch", key="basket_comparison", column_config={
            "drawdown": st.column_config.NumberColumn("Drawdown", format="%.1f%%"),
            "Eligible members": st.column_config.NumberColumn(format="%d"),
        })
        st.caption("Basket values are medians of eligible members; ARKK is a single ETF used as an external audit reference. ARKK does not set the dial. Missing values remain unavailable.")
    with ratios_tab:
        cards = st.columns(2)
        cards[0].metric("Credit status", text(latest["credit_status"]))
        cards[1].metric("Concentration broken", flag_text(latest["is_concentration_broken"], yes="Yes", no="No"))
        ratios = history[["trade_date", "credit_distance", "concentration_distance"]].melt(
            id_vars="trade_date", var_name="Series", value_name="Distance",
        ).dropna(subset=["Distance"])
        ratios["Series"] = ratios["Series"].map({
            "credit_distance": "Credit: HYG / IEF",
            "concentration_distance": "Concentration: SPY / RSP",
        })
        if ratios.empty:
            st.info("Credit and concentration history is not available.")
        else:
            chart = alt.Chart(ratios).mark_line().encode(
                x=alt.X("trade_date:T", title="Trading date"),
                y=alt.Y("Distance:Q", title="Distance from 126-day high", axis=alt.Axis(format=".0%")),
                color=alt.Color("Series:N", legend=alt.Legend(orient="top")),
                tooltip=[alt.Tooltip("trade_date:T", title="Date"), "Series:N", alt.Tooltip("Distance:Q", format=".1%")],
            ).properties(height=240)
            st.altair_chart(chart, width="stretch")
        st.caption("Each ratio is measured against its own 126-trading-day high. Credit watch starts at -3%, stress at -6%; concentration is marked broken at -5%. These thresholds come from the frozen methodology.")


def show_episodes(episodes):
    st.subheader("Divergence episode history")
    if episodes.empty:
        st.info("No divergence episodes are available yet.")
        return
    table = episodes.sort_values("start_date", ascending=False).copy()
    table["Status"] = table["is_open"].map(lambda value: flag_text(value, yes="Open", no="Closed"))
    table["Confirmed"] = table["is_held"].map(lambda value: flag_text(value, yes="Yes", no="No"))
    for column in ["start_date", "end_date", "held_date", "disarm_date"]:
        table[column] = pd.to_datetime(table[column], errors="coerce").dt.date
    st.dataframe(
        table[["start_date", "end_date", "Status", "trading_days", "max_divergence_run", "Confirmed", "held_date", "disarm_date"]],
        hide_index=True, width="stretch", key="episode_history", column_config={
            "Confirmed": "Confirmed (held)",
            "start_date": st.column_config.DateColumn("Episode start", format="YYYY-MM-DD"),
            "end_date": st.column_config.DateColumn("Episode end", format="YYYY-MM-DD"),
            "trading_days": "Span trading days", "max_divergence_run": "Longest divergence run",
            "held_date": st.column_config.DateColumn("Confirmed on", format="YYYY-MM-DD"),
            "disarm_date": st.column_config.DateColumn("Disarmed on", format="YYYY-MM-DD"),
        },
    )
    st.caption("Confirmation (held) requires 15 consecutive divergence trading days. A closed episode can still leave the armed clock active; use the verdict's armed-since date for the current state.")
    calculated = pd.to_datetime(episodes["computed_at"], utc=True, errors="coerce").max()
    if pd.notna(calculated):
        st.caption(f"Episode records calculated at: {calculated:%Y-%m-%d %H:%M UTC}. This panel shows the current episode build and is not changed by the History filter.")


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
            st.dataframe(events[["trade_date", "Event"]], hide_index=True, width="stretch", key="arming_events")


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
        table, hide_index=True, width="stretch", key="member_details",
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
        load_episodes.clear()
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
    try:
        members = load_members(PROJECT, DATASET, LOCATION, as_of)
    except Exception:
        LOGGER.exception("Could not load member drawdowns")
        members = None

    cards = st.columns(4)
    cards[0].metric("Dial level", f"{count(latest['dial_level'])} / 5")
    cards[0].caption(text(latest["dial_label"]))
    cards[1].metric("Credit status", text(latest["credit_status"]))
    armed = latest["is_armed"]
    armed_since = "Not armed" if pd.notna(armed) and not bool(armed) else text(latest["armed_since"])
    cards[2].metric("Armed since", armed_since)
    cards[3].metric("Speculative broken / eligible", f"{count(latest['spec_members_broken'])} / {count(latest['spec_members_valid'])}")
    st.info(text(latest["dial_explanation"]))
    badge = latest["badge"]
    if pd.notna(badge):
        st.caption("Pattern qualifier: " + BADGE_LABELS.get(badge, str(badge)))
    show_basket_qualifier(latest, members)

    show_evidence(latest)
    history = signals if history_days == "All" else signals.loc[
        signals["trade_date"] >= latest["trade_date"] - pd.Timedelta(days=history_days)
    ]
    show_history(history)
    show_market_context(latest, history)
    if members is None:
        st.error("Member data could not be loaded for the verdict date. The verdict above is from daily_signals.")
    elif members.empty:
        st.info("No member data are available for the verdict date.")
    else:
        show_members(members, as_of)

    try:
        episodes = load_episodes(PROJECT, DATASET, LOCATION, as_of)
        show_episodes(episodes)
    except Exception:
        LOGGER.exception("Could not load episodes")
        st.error("Episode history could not be loaded. The verdict and other available views remain visible.")

    with st.expander("Recent readings"):
        st.dataframe(signals[["trade_date", "dial_level", "dial_label", "credit_status"]].tail(10), hide_index=True, key="recent_readings")
    st.subheader("How to read this")
    st.write(
        "Start with the dial and its explanation. Levels run from 0 CALM through 1 STRAIN, "
        "2 DIVERGENCE, 3 TOPPING, 4 REPRICING, and 5 WASHOUT. Breadth measures how many "
        "eligible speculative names are at least 25% below their reference highs. Compare it "
        "with the S&P's distance from its high, then inspect member drawdowns and credit status. "
        "Badges qualify unusual patterns. With complete prices, an ARKK disagreement is labeled AI-specific; otherwise check the data and basket. "
        "N/A means unavailable, and a historical reading describes its displayed date."
    )


dashboard()
