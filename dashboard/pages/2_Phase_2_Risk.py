"""Phase 2 preview using the unmodified PR #99 contract fixtures."""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="AI stock risk · Phase 2", layout="wide")
st.title("AI stock risk · Phase 2")
st.warning("DUMMY DATA — All probabilities, ranks and evaluation results below are made up. This is a layout preview, not model output.")
st.caption("Contract v0.3 draft · PR #99 · fixture version dummy-0")

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "phase2"


@st.cache_data
def load_preview():
    return {name: pd.read_csv(ROOT / f"{name}.csv") for name in
            ("model_scores", "model_evaluation", "universe_dial_daily", "weekly_features")}


data = load_preview()
scores = data["model_scores"]
week = st.selectbox("Weekly score date", sorted(scores.as_of.unique(), reverse=True))
latest = scores.loc[scores.as_of.eq(week)].copy()
basket = latest.loc[latest.role.eq("our_basket")].sort_values("prob_drop_20pct_60d", ascending=False)
universe = latest.loc[latest.role.eq("universe")]
expected = sorted(data["weekly_features"].loc[lambda d: d.role.eq("our_basket"), "ticker"].unique())
missing = sorted(set(expected) - set(basket.ticker))

st.header("Risk compared with the wider AI universe")
st.write("Estimated chance that the lowest closing price in the next 60 trading days is at least 20% below the score-date closing price.")
if basket.empty or universe.empty:
    st.info("A basket and a universe comparison require scores for the same week.")
else:
    a, b, c = st.columns(3)
    bm = basket.prob_drop_20pct_60d.median()
    um = universe.prob_drop_20pct_60d.median()
    a.metric("Basket median probability", f"{bm:.1%}")
    b.metric("Universe median probability", f"{um:.1%}")
    c.metric("Median difference", f"{(bm-um)*100:+.1f} pp")
    comparison = "higher" if bm > um else "lower" if bm < um else "equal"
    st.info(f"In this dummy example, the scored basket's median risk is {comparison} than the universe median. Coverage: {len(basket)}/{len(expected)} basket names; {len(universe)} universe names.")
    plot = latest.assign(Population=latest.role.map({"our_basket": "Our basket", "universe": "AI universe"}))
    chart = alt.Chart(plot).mark_circle(size=100, opacity=.8).encode(
        x=alt.X("prob_drop_20pct_60d:Q", title="Predicted drop probability", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        y=alt.Y("Population:N", title=None), color=alt.Color("Population:N", title="Population"),
        tooltip=["ticker", alt.Tooltip("prob_drop_20pct_60d:Q", format=".1%"), "rank_in_universe"])
    medians = plot.groupby("Population", as_index=False).prob_drop_20pct_60d.median()
    marks = alt.Chart(medians).mark_tick(thickness=4, size=65, color="#222222").encode(
        x="prob_drop_20pct_60d:Q", y="Population:N",
        tooltip=["Population", alt.Tooltip("prob_drop_20pct_60d:Q", title="Median", format=".1%")])
    st.altair_chart((chart + marks).properties(height=200), use_container_width=True)
    st.caption("Black markers show each group's median. Hover over a dot to identify the stock.")
    table = basket[["ticker", "prob_drop_20pct_60d", "rank_in_universe", "universe_size", "prob_change_1w"]].copy()
    table["Probability"] = table.prob_drop_20pct_60d.map(lambda x: f"{x:.1%}")
    table["Universe insertion rank"] = table.apply(lambda r: f"{int(r.rank_in_universe)} / {int(r.universe_size)}", axis=1)
    table["Comparison"] = table.rank_in_universe.map(lambda r: "Above all scored universe names" if r == 1 else f"{int(r)-1} universe names have higher risk")
    table["Weekly change"] = table.prob_change_1w.map(lambda x: "N/A — first scored week" if pd.isna(x) else f"{100*x:+.1f} pp")
    st.dataframe(table[["ticker", "Probability", "Comparison", "Universe insertion rank", "Weekly change"]], hide_index=True)
    st.caption("Rank 1 is highest risk. Basket ranks indicate where each name would sit among universe names; ties can share a rank. Weekly changes are percentage points.")
    selected = st.selectbox("Stock probability history", basket.ticker.tolist())
    history = scores.loc[scores.ticker.eq(selected) & scores.as_of.le(week)].copy()
    history["as_of"] = pd.to_datetime(history.as_of)
    st.altair_chart(alt.Chart(history).mark_line(point=True).encode(
        x=alt.X("as_of:T", title="Score date"),
        y=alt.Y("prob_drop_20pct_60d:Q", title="Predicted probability", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("model_version:N", title="Model version"),
        tooltip=["ticker", "as_of:T", alt.Tooltip("prob_drop_20pct_60d:Q", format=".1%")]
    ).properties(height=180), use_container_width=True)
    st.caption("Two dummy weeks illustrate navigation, not a reliable trend. Model changes can also change probabilities.")
if missing:
    st.info("Not scored: " + ", ".join(missing) + ". SPCX has insufficient history under the 126-trading-day rule. No missing score is treated as zero risk.")

st.header("Robustness check")
dials = data["universe_dial_daily"].sort_values("trade_date")
dials = dials.loc[dials.trade_date.le(week)]
if dials.empty:
    st.info("No dial reading is available on or before the selected score date.")
else:
    dial = dials.iloc[-1]
    st.caption(f"Daily dial date: {dial.trade_date}. Latest available reading on or before the selected weekly score date.")
    labels = {0: "CALM", 1: "STRAIN", 2: "DIVERGENCE", 3: "TOPPING", 4: "REPRICING", 5: "WASHOUT"}
    left, right = st.columns(2)
    level = int(dial.official_dial_level)
    left.metric("Official dial", f"{level} · {labels.get(level, 'Unknown')}")
    right.metric("Larger-basket dial", f"{int(dial.universe_dial_level)} · {dial.universe_dial_label}")
st.write("Agreement suggests the pattern extends beyond our selected basket; disagreement suggests the reading depends on basket composition. Neither establishes predictive accuracy.")
st.caption("Dummy fixtures use 118 valid dial members and 9 scored universe names; they are illustrative populations, not the final selected universe.")

st.header("Model card")
model = latest.iloc[0]
evaluation = data["model_evaluation"]
st.caption("Evaluation below is retrospective for this model version; it was not necessarily available on the selected historical score date.")
auc = evaluation.loc[evaluation.split.eq("test") & evaluation.population.eq("universe") & evaluation.metric.eq("auc") & evaluation.model_version.eq(model.model_version)]
served = auc.loc[auc.model_name.eq(model.model_name)]
st.write(f"Served model: **{model.model_name}** · Version: **{model.model_version}**")
st.write("Last trained: **Unavailable — trained_at is not yet provided by contract v0.3.**")
st.caption(f"Scores produced: {model.scored_at}. Scoring time is not training time.")
if served.empty:
    st.info("No matching test evaluation is available for this model version.")
else:
    row = served.iloc[0]
    st.metric("Test AUC · universe", f"{row.value:.3f}")
    if pd.notna(row.ci_low) and pd.notna(row.ci_high):
        st.caption(f"90% block-bootstrap interval: {row.ci_low:.3f}–{row.ci_high:.3f}; {int(row.n_weeks)} weeks, {int(row.n_rows)} rows.")
    baselines = auc.loc[auc.model_name.isin(["baseline_drawdown", "baseline_vol"])]
    if not baselines.empty:
        best = baselines.sort_values("value", ascending=False).iloc[0]
        st.write(f"Best simple baseline: **{best.model_name}**, AUC **{best.value:.3f}**.")
    beat = row.beats_best_baseline
    if pd.isna(beat):
        st.info("Baseline superiority has not been established for the served model.")
    elif str(beat).lower() == "true":
        st.success("Dummy evaluation reports an improvement over the best baseline.")
    else:
        st.info("Dummy evaluation does not establish an improvement over the best baseline, even if the point estimate is higher.")
    st.caption(f"Evaluated: {row.evaluated_at}. Historical test performance does not validate outcomes for newly issued forecasts.")
    comparison = evaluation.loc[evaluation.split.eq("test") & evaluation.population.eq("universe") & evaluation.model_version.eq(model.model_version)]
    comparison = comparison.loc[comparison.model_name.isin([model.model_name, "baseline_drawdown", "baseline_vol"])]
    comparison = comparison.pivot(index="model_name", columns="metric", values="value")
    st.dataframe(comparison.reindex(columns=["auc", "precision_top_decile", "brier"]).round(3), hide_index=False)
    st.caption("AUC measures discrimination, not accuracy. Top-decile precision measures events among the highest-risk 10%; Brier measures probability error (lower is better).")
st.caption("Known limits: a current ETF-holdings universe introduces hindsight and survivorship bias; stocks and overlapping forward windows are dependent. All figures on this page are dummy examples.")
