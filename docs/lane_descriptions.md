# Phase 1 lane descriptions

BA882 Fall 2026 · updated October 8, 2026

This note expands the five Phase 1 lanes so everyone can pick with full information. Each lane lists its mission, concrete tasks, what it produces for and consumes from the other lanes, its dates, and what “done” means at the October 27 presentation. Every lane builds against the schema contract we freeze on Saturday, October 10 (end of week one), so no lane waits on another lane's finished work. The Methodology tab is the authoritative specification for everything Lane 3 computes.

## Lane 1 · Ingestion and orchestration

Get market data landing in our cloud reliably, every trading day, without a human touching it.

### What this lane owns

The extractor code, its Docker image, the Airflow DAG, and the Astronomer deployment.

### Tasks

- **Extractor:** Python job pulling daily adjusted closes for all 22 tickers (the speculative basket of 11, the 7 mega caps, S&P 500, ARKK, HYG, IEF, SPY, RSP) from yfinance, writing raw files to a GCS landing zone partitioned by date.
- **Fallback source:** Second provider (Alpha Vantage or Tiingo free tier) behind the same interface, used when Yahoo rate-limits or errors; log which source served each run.
- **Idempotency:** Re-running a date must not duplicate rows: overwrite the partition or merge on (date, ticker).
- **Docker:** Package the extractor; the same image runs locally and in the DAG.
- **Airflow DAG:** Daily schedule on Astronomer: extract, load to BigQuery raw, trigger dbt, with retries and clear task boundaries.
- **Alerting:** Failure notification (email or Slack webhook) when any task fails; this is the observability item the syllabus asks for.
- **Backfill:** One-off job loading two years of history so signals have full reference windows from day one.

### Interfaces

- **Produces:** prices\_raw table in BigQuery, fresh by market close + 2 hours each trading day; run logs visible in Astronomer.
- **Consumes:** The schema contract (column names and types for prices\_raw) from Lane 3.

### Key dates for this lane

- Oct 12 (Mon): raw prices landing in BigQuery; manual trigger is fine
- Oct 15 (Thu): two-year backfill loaded; DAG scheduled on Astronomer
- Oct 17 (Sat): two consecutive green scheduled runs; failure alert tested
- Oct 23 (Fri): feature freeze

### Definition of done (Oct 27)

- DAG green for at least five consecutive trading days before Oct 27.
- A deliberately failed run produces an alert and a readable log we can show in the demo.
- README section: how to trigger a backfill.

### Skills and course material it leans on

Sessions 1–4; DataCamp: Intro to Shell, GitHub, Airflow. Comfort with Python and APIs helps most.

## Lane 2 · Warehouse and dbt

Turn raw landed data into trustworthy, tested tables the rest of the project reads.

### What this lane owns

The BigQuery datasets, the dbt project, staging models, and the data quality test suite.

### Tasks

- **Datasets:** BigQuery structure (raw, staging, marts) with permissions so every member can query and the service account can write.
- **dbt project:** Initialize, declare sources over prices\_raw, set up profiles for local runs and the DAG-triggered runs.
- **Staging models:** Typed, deduplicated, renamed staging layer: one row per ticker per trading day; flag too-new tickers explicitly (the maturity and IPO-seasoning rules themselves live in Lane 3's marts, per the Methodology).
- **Basket membership table:** Seed basket\_members as a slowly changing dimension: ticker, basket, added\_date, removed\_date, reason; membership rules documented in the model's YAML. The founding roster of eleven is tabulated in the Methodology tab, section 4.
- **Tests:** dbt tests for not-null, uniqueness on (date, ticker), accepted ranges, and freshness on the source; failures must fail the DAG run visibly.
- **Docs:** dbt docs generated so the lineage graph can be shown at the presentation.

### Interfaces

- **Produces:** Clean staging tables and basket\_members; the dbt skeleton Lane 3 adds marts into.
- **Consumes:** Raw tables from Lane 1; the schema contract from Lane 3.

### Key dates for this lane

- Oct 9 (Fri): comments on the draft schema contract
- Oct 12 (Mon): dbt initialized; first staging model builds
- Oct 14 (Wed): basket\_members seeded, with tests
- Oct 17 (Sat): all staging models and tests green on the scheduled run

### Definition of done (Oct 27)

- dbt build passes with all tests green on the daily schedule.
- Lineage graph renders and is in the demo script.
- A seeded bad row demonstrably fails a test (for the observability story).

### Skills and course material it leans on

Sessions 2–4; DataCamp: Data Warehousing, Intro + Intermediate dbt. The SQL-strongest member thrives here.

## Lane 3 · Signal logic

Encode the bubble methodology as SQL marts so the warehouse, not a laptop script, computes the signal.

### What this lane owns

The marts layer: daily\_drawdowns, daily\_signals (condition flags, dial, badge, armed), episodes, credit\_daily; the schema contract; and the fixture-based validation.

### Tasks

- **Schema contract:** Draft the column contracts for all six tables (prices\_raw, basket\_members, daily\_drawdowns, daily\_signals, episodes, credit\_daily) in week one, written directly from Methodology section 6, and circulate for the Oct 10 freeze; this unblocks every other lane.
- **Drawdown mart:** Per ticker per day: reference high (available history capped at 252 trading days, with a listing's first 20 days excluded), reference-window length, drawdown, 60-day maturity flag, broken flag.
- **Signals mart:** Breadth, median member drawdown, S&P distance from high, the condition flags from the Methodology's condition matrix, the dial level (0 to 5), the badge, and the armed flag with armed-since, including the confirmation-period and quiet-month expiry logic.
- **Episodes mart:** Contiguous divergence spans with start, end, held flag, and maximum intensity; reset when breadth falls back below 30%.
- **Credit mart:** HYG/IEF ratio and its distance from the rolling 126-day high, with WATCH and STRESS flags.
- **Validation fixtures:** Hand-built synthetic price histories with expected drawdowns, breadth, arming, and dial levels computed by hand for a dozen dates; dbt tests assert the Methodology's condition matrix cell by cell. The fixture file is the validation evidence for the demo.
- **Decision log:** Write the one-page why-answers (why breadth over a basket average, why these tickers, thresholds' provenance).
- **Methodology narrative:** Co-write the methodology portion of the Oct 27 presentation with Lane 5 and field the “why” questions in the stakeholder Q\&A; Lane 5 owns deck production and logistics.

### Interfaces

- **Produces:** The marts the dashboard reads; the schema contract everyone builds against.
- **Consumes:** Staging tables and basket\_members from Lane 2.

### Key dates for this lane

- Oct 8 (Thu): draft schema contract circulated for comment
- Oct 10 (Sat): schema contract FROZEN — the chokepoint every other lane waits on
- Oct 15 (Thu): validation fixtures written (synthetic prices plus hand-computed expected outputs)
- Oct 17 (Sat): all marts building
- Oct 19 (Mon): marts match the fixtures; condition matrix asserted cell by cell
- Oct 22 (Thu): decision log v1 committed

### Definition of done (Oct 27)

- Marts match the fixtures, with every condition-matrix cell asserted by a dbt test.
- The dial level for “today” is queryable with one SELECT.
- Decision log v1 committed.

### Skills and course material it leans on

Window functions in SQL are the core skill. Deepest methodology knowledge lives here; Javier takes this lane.

## Lane 4 · Dashboard

Make the signal legible in five seconds to someone who has never heard of Grantham.

### What this lane owns

The Looker or Streamlit app and its deployment.

### Tasks

- **Tool decision:** Pick Looker (easiest BigQuery connection, instructor-endorsed) or Streamlit on Cloud Run (more control); decide by Oct 10 and record it in the decision log.
- **Verdict cards:** Top of the page answers the question directly: the dial level with its one-sentence explanation, the badge, armed-since, and credit status; charts support, they do not lead.
- **Charts:** Breadth versus S&P distance-from-high (the divergence itself), member drawdowns, and the dial history strip; all reading from marts, no computation in the dashboard layer.
- **Ticker table:** Per-member drawdown and 6-month return, sorted worst first, broken members flagged.
- **Dummy-data start:** Build against seeded rows from the schema contract in week one; swap to real marts in week two without layout changes.
- **Peer usability:** Another team will click around during evaluations: label everything, add a one-paragraph “how to read this” note on the page.

### Interfaces

- **Produces:** The thing the audience sees; the demo centerpiece.
- **Consumes:** Marts from Lane 3; the schema contract for week-one dummy rows.

### Key dates for this lane

- Oct 10 (Sat): Looker vs Streamlit decision recorded
- Oct 12 (Mon): dashboard skeleton on seeded dummy rows
- Oct 19 (Mon): v1 reading real marts
- Oct 23 (Fri): polish freeze

### Definition of done (Oct 27)

- Dashboard loads from live marts with zero manual steps.
- A stranger can state the current dial level in one sentence after ten seconds.
- Linked from the repo README.

### Skills and course material it leans on

Session 5 (BI tools, Streamlit, Looker). Strong product taste matters more than heavy coding.

## Lane 5 · Platform and PM

Make the project look and run like an engineering organization, which the course grades directly.

### What this lane owns

Repo, project board, GCP administration, IaC, the presentation, and the AI-use appendix.

### Tasks

- **Repo and board:** GitHub repo with branch protection, PR template, and a project board with the five lanes as swimlanes; issues created from the milestone checklists.
- **GCP admin:** Project creation, IAM roles per member, service accounts for the DAG, billing alerts before any credits burn.
- **IaC:** Terraform for the BigQuery datasets and GCS buckets at minimum, shown in session 6 spirit; point-and-click only where Terraform is disproportionate.
- **Integration owner:** Run the Oct 20 in-class session as the integration checkpoint with a written punch list.
- **Presentation:** Own deck production, demo logistics and rehearsal for Oct 27, with a recorded fallback demo in case live GCP misbehaves; the methodology narrative comes from Lane 3.
- **AI appendix:** Running log of prompts, tools and versions from day one, as the syllabus requires.

### Interfaces

- **Produces:** The repo everyone works in; the presentation; the paper trail.
- **Consumes:** Status from every lane, weekly.

### Key dates for this lane

- Oct 7 (Wed): repo and project board live
- Oct 9 (Fri): GCP project, IAM, service accounts, billing alerts
- Oct 12 (Mon): every lane broken into GitHub issues
- Oct 20 (Tue): integration session run with a written punch list
- Oct 24 (Sat): full rehearsal; Oct 26 (Mon): fallback demo recorded

### Definition of done (Oct 27)

- Board reflects reality (the instructor checks how the project is managed).
- Deck and fallback demo rehearsed once end to end before Oct 27.
- AI appendix current through week three.

### Skills and course material it leans on

Project management instincts, GitHub fluency, and calendar discipline.

## Schedule and dependencies

Everything in one place, sorted by date. The “Depends on” column is the dependency map: before starting your item, check that what it depends on has landed, and if it has not, escalate in the team channel that day rather than silently waiting.

| Date | Lane | Deliverable | Depends on |
| --- | --- | --- | --- |
| Oct 7 (Wed) | 5 | Repo and project board live, lanes as swimlanes | None |
| Oct 8 (Thu) | All | Lane owners named in the shared doc | None |
| Oct 8 (Thu) | 3 | Draft schema contract circulated | None |
| Oct 9 (Fri) | 5 | GCP project, IAM, service accounts, billing alerts | None |
| Oct 9 (Fri) | 1, 2, 4 | Comments on the draft contract | Draft (Lane 3, Oct 8) |
| Oct 10 (Sat) | 3 | SCHEMA CONTRACT FROZEN — the chokepoint | Comments from Lanes 1, 2, 4 |
| Oct 10 (Sat) | 4 | Looker vs Streamlit decision recorded | None |
| Oct 12 (Mon) | 1 | Raw prices landing in BigQuery (manual trigger fine) | GCP access (L5, Oct 9); contract (L3) |
| Oct 12 (Mon) | 2 | dbt initialized; first staging model builds | Raw table (L1); contract (L3) |
| Oct 12 (Mon) | 4 | Dashboard skeleton on seeded dummy rows | Contract (L3) |
| Oct 12 (Mon) | All | Own lane broken into GitHub issues with acceptance criteria | Board (L5, Oct 7) |
| Oct 14 (Wed) | 2 | basket\_members seeded, with tests | Contract (L3) |
| Oct 15 (Thu) | 1 | Two-year backfill loaded; DAG scheduled on Astronomer | Raw pipeline (Oct 12) |
| Oct 15 (Thu) | 3 | Validation fixtures written (synthetic prices + expected outputs) | Contract (L3) |
| Oct 17 (Sat) | 2 | All staging models and tests green on schedule | Scheduled DAG (L1, Oct 15) |
| Oct 17 (Sat) | 3 | All marts building | Staging models (L2) |
| Oct 19 (Mon) | 3 | Marts match fixtures; condition matrix asserted cell by cell | Fixtures (Oct 15); marts (Oct 17) |
| Oct 19 (Mon) | 4 | Dashboard v1 on real marts | Marts (L3, Oct 17) |
| Oct 20 (Tue) | All | Integration session in class; punch list written (L5). Quiz 2 same day | End-to-end flow from the rows above |
| Oct 22 (Thu) | 3 | Decision log v1 committed | None |
| Oct 23 (Fri) | All | Feature freeze | Punch list items closed |
| Oct 24 (Sat) | 5 | Full rehearsal; Oct 26 (Mon) fallback demo recorded | Freeze (Oct 23) |
| Oct 27 (Tue) | All | Phase 1 presentation | Everything above |

## How the lanes fit together

Lane 1 lands raw data, Lane 2 cleans and tests it, Lane 3 turns it into the signal, Lane 4 shows it, and Lane 5 keeps the machine and the story running. The schema contract (frozen Oct 10) is the only hard dependency between lanes in week one; after that, integration happens continuously through the shared warehouse rather than in a single scary merge.

## After Phase 1

Lanes rotate at each phase boundary, so picking a Phase 1 lane is a three-week commitment, not a semester identity. Phase 2 (Nov 10 to 24) centers on a new MLOps lane: the feature table built from our signals, MLflow-tracked training of the drawdown-probability model, and serving it on Cloud Run. Phase 3 (Nov 24 to Dec 8) adds a GenAI lane: news ingestion and LLM classification, the vector store over company filings, and the auto-generated weekly brief. Ingestion and platform shrink to maintenance once the pipelines run, which frees people for the new lanes. We will write the detailed plan for each phase the week before it starts, with the lessons from the previous one in hand; anyone who wants the ML or GenAI lane for their recruiting story should say so early.

Claiming a lane: put your name in the Owner column of the Phase 1 plan tab by Thursday, October 8. If two people want the same lane, the tiebreaker is who needs the skill more for their recruiting story.
