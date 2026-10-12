# BA882 Team Project Proposal: AI Bubble Early-Warning System

Oct 6, 2026 · @Javier

## The idea

We build a cloud early-warning system that watches for the market pattern that preceded the 1929, 1972, 2000 and 2021 crashes, applied to today's AI stocks. Investor Jeremy Grantham (who called both the dot-com and 2008 busts) documented the pattern: months before a bubble tops, the riskiest and most hyped stocks start falling in absolute terms while the overall index keeps setting record highs, because professionals quietly rotate out of speculative names first.

Nobody publishes a live, open tracker of this signal. Banks like Goldman Sachs maintain similar speculative baskets behind paywalls. Our pipeline computes the signal daily from free market data and raises a flag when the historical danger pattern appears. The instructor's own tip says novel projects earn interview calls; "I built a production early-warning system for the AI bubble" is a story every team member can tell in spring recruiting.

## Methodology: how we identify the bubble top

The system tracks three groups daily: a basket of eleven speculative AI names (CoreWeave, Nebius, SpaceX, SMCI, the data-center builders, small-cap AI story stocks), the seven mega-cap AI spenders (Microsoft, Nvidia, Oracle and peers), and the S&P 500. The Methodology tab is the authoritative specification; in brief, the logic has three layers:

1. **Conditions.** Named facts about today's prices: the **divergence** condition (50%+ of the basket broken 25%+ below their highs, median member down 15%+, while the S&P sits within 5% of its record; the Grantham pattern), **deterioration**, **repricing**, **washout**, and a **credit gauge** (HYG/IEF).
2. **Memory.** The system **arms** when the divergence condition holds for 15 consecutive trading days, filtering whipsaws like the Feb to Apr 2026 selloff that fully reversed in May. Armed lasts 18 quiet months (capped at 36 calendar months) and means the junk-first breakdown is on record, so later weakness reads as the historical sequence; historically the index top arrived 6 to 18 months after the junk first cracked.
3. **The dial.** One output, 0 to 5: CALM, STRAIN, DIVERGENCE, TOPPING, REPRICING, WASHOUT. Levels 3+ are reachable only while armed; a market decline without the armed precedent shows a Level 1 **off-pattern** badge instead of climbing the dial.

## Fit with the BA882 hard requirements

| Requirement | How this project meets it |
| --- | --- |
| Data feed updates at least weekly | Market prices update daily (trading days); news feeds for Phase 3 update continuously |
| 5+ warehouse tables, 3+ appending via pipelines | prices\_raw, basket\_members (slowly changing dimension with changelog), daily\_drawdowns, daily\_signals (condition flags, dial level, badge, armed), episodes, credit\_daily, plus news\_items and llm\_enrichments in Phase 3; prices\_raw, daily\_drawdowns, daily\_signals and credit\_daily append every run |
| Deployed in the cloud, pipelines and logs visible | GCP stack: BigQuery warehouse, Airflow on Astronomer for the daily DAG, dbt for transformations and data quality tests, Looker or Streamlit for the dashboard |

The basket membership table is a genuine dbt teaching case: members enter and exit on documented rules, never because they fell, so history stays honest. To de-risk Yahoo Finance rate limits on automated pulls, we add a fallback price source (for example Alpha Vantage or Tiingo), which also demonstrates multi-source ingestion.

## Phases and deliverables

&#91;embedded content: course phases and graded gates · Fall 2026\]

Each course phase productionizes one layer of the system; the presentations on Oct 27 and Dec 8 are the graded gates.

| Course phase | What we build | Deliverable at the gate |
| --- | --- | --- |
| 1 · Data pipelines + reporting | Scheduled Airflow + dbt pipeline populating BigQuery (5+ tables), signal computation, dashboard in Looker or Streamlit | Live cloud dashboard showing the daily signal, repo walkthrough, peer demo |
| 2 · MLOps | Feature table from our signals; MLflow-tracked model predicting the probability of a 5%+ index drawdown over 20 trading days; served on Cloud Run | Model API the dashboard calls, with training pipeline and evaluation runs |
| 3 · GenAI workflows | News ingestion per basket ticker, LLM headline classification, vector store over company filings, auto-generated weekly "state of the bubble" brief | RAG application plus the generated brief, demoed at final presentations |

## Data sources and team split

Sources: Yahoo Finance (daily prices for all tickers, with a fallback provider), FRED (10-year Treasury, high-yield spreads), SEC EDGAR (hyperscaler filings for Phase 3 retrieval), and news/RSS feeds per basket company (Phase 3 LLM classification).

The work splits into four lanes, so nobody is a passenger: ingestion and orchestration (Airflow DAGs, source APIs, Docker), warehouse and modeling (BigQuery, dbt models and tests), MLOps (feature tables, MLflow training runs, model serving), and GenAI (news classification pipeline, vector store, RAG brief generator). Each lane owns its slice of the GitHub project board, which the course grades directly.

Lane assignments and weekly milestones: Phase 1 plan
