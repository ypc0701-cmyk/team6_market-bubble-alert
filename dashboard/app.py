import os

import pandas as pd
import streamlit as st
from google.cloud import bigquery

PROJECT = "market-bubble-alert"
DATASET = os.getenv("BQ_DATASET", "marts_dev")

if DATASET not in {"marts_dev", "marts"}:
    raise ValueError("BQ_DATASET must be marts_dev or marts")

st.set_page_config(page_title="Market Bubble Alert", layout="wide")
st.title("Market Bubble Alert")
st.caption("Daily market-pattern monitoring for the selected AI stock basket.")
st.sidebar.write(
    "Development data" if DATASET == "marts_dev" else "Production data"
)


@st.cache_data(ttl=60)
def load_signals(dataset):
    client = bigquery.Client(project=PROJECT)
    sql = f"""
        SELECT trade_date, dial_level, dial_label, dial_explanation,
               badge, armed_since, credit_status,
               spec_members_broken, spec_members_valid,
               breadth, spx_distance, basket_audit_flag, computed_at
        FROM `{PROJECT}.{dataset}.daily_signals`
        ORDER BY trade_date
    """
    config = bigquery.QueryJobConfig(
        maximum_bytes_billed=1_000_000_000
    )
    rows = client.query(
        sql, location="US", job_config=config
    ).result()
    return pd.DataFrame([dict(row.items()) for row in rows])


if st.sidebar.button("Refresh data"):
    load_signals.clear()

try:
    signals = load_signals(DATASET)
except Exception as error:
    st.error("Signal data could not be loaded. Check access and dataset.")
    st.code(str(error))
    st.stop()

if signals.empty:
    st.info("No signal rows are available yet.")
    st.stop()

signals["trade_date"] = pd.to_datetime(signals["trade_date"])
latest = signals.iloc[-1]

st.caption(f"Data as of: {latest['trade_date']:%Y-%m-%d}")
st.caption(f"Calculated at: {latest['computed_at']}")

cards = st.columns(4)
cards[0].metric("Risk level", f"{int(latest['dial_level'])} / 5")
cards[0].caption(str(latest["dial_label"]))
cards[1].metric("Credit status", str(latest["credit_status"]))

armed = latest["armed_since"]
cards[2].metric(
    "Episode start",
    str(armed) if pd.notna(armed) else "Not armed",
)
cards[3].metric(
    "Broken / eligible names",
    f"{int(latest['spec_members_broken'])} / "
    f"{int(latest['spec_members_valid'])}",
)

st.info(str(latest["dial_explanation"]))

if pd.notna(latest["badge"]):
    st.write("Pattern qualifier:", latest["badge"])

if latest["basket_audit_flag"]:
    st.warning(
        "Basket audit: the selected AI basket differs materially from ARKK."
    )

st.subheader("Breadth and S&P distance from high")
st.caption("Values are decimal fractions: 0.10 means 10%.")
st.line_chart(
    signals.set_index("trade_date")[["breadth", "spx_distance"]]
)

st.subheader("Recent readings")
st.dataframe(
    signals[
        ["trade_date", "dial_level", "dial_label", "credit_status"]
    ].tail(10),
    hide_index=True,
)
