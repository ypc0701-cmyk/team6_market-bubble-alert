# Phase 1 plan

Oct 6, 2026 · three weeks to the Phase 1 presentations on Oct 27, 2026

Five lanes, one owner each. Put your name in the Owner column by Thursday, Oct 8. The schema freeze on Oct 10 (end of week one) unblocks every lane. Dated deliverables per lane and the full dependency table are in the Lane descriptions tab.

## The five lanes

| Lane | Scope | Owner |
| --- | --- | --- |
| 1 · Ingestion + orchestration | Extractor for daily prices (yfinance + fallback source) into a GCS landing zone; Dockerized; scheduled as an Airflow DAG on Astronomer | Kean |
| 2 · Warehouse + dbt | BigQuery datasets; dbt project structure; staging models from raw; data quality tests (nulls, freshness, duplicate dates) | Ahrar |
| 3 · Signal logic | Drawdown, breadth, armed and dial math as dbt marts, built from scratch per the Methodology tab; validated against hand-built fixtures (condition matrix asserted cell by cell) | Javier |
| 4 · Dashboard | Looker or Streamlit app reading the marts; built around verdict cards (dial level, badge, armed-since, credit) rather than raw tables | Yuanhao |
| 5 · Platform + PM | GitHub repo and project board; GCP project, IAM, billing alerts; light Terraform; presentation and demo script | Chloe |

Every lane builds against the frozen schema, not against another lane's finished work.

## Dependency chain

- **Schema contract (Lane 3, frozen Oct 10)** is the chokepoint: Lane 1's load shape, Lane 2's staging, and Lane 4's dummy-data build all start from it.
- **Data flow:** Lane 1 raw (Oct 12) → Lane 2 staging green (Oct 17) → Lane 3 marts (Oct 17) → Lane 4 dashboard on real data (Oct 19).
- **Validation path:** Lane 3 fixtures written (Oct 15) → marts match fixtures and the condition matrix, cell by cell (Oct 19). Lane 1's backfill (Oct 15) feeds the armed history.
- **Platform first:** Lane 5 repo and GCP access (Oct 7 to 9) precede everyone's first commit.
- Blocked by a missing dependency? Escalate in the team channel that day; silent waiting is how week 3 gets ugly.

## Milestones

**Week 1 · Oct 6 to 12 · everything stands up**

- [ ] Repo + GitHub project board created, lanes as swimlanes (lane 5, Oct 7)
- [ ] GCP project, service accounts, billing alerts (lane 5, Oct 9)
- [ ] Schema contract for the five tables frozen and committed, Oct 10 (all, lane 3 drafts by Oct 8)
- [ ] Extractor lands raw prices in BigQuery, manual trigger is fine (lane 1, Oct 12)
- [ ] dbt initialized: sources declared, one staging model building (lane 2, Oct 12)
- [ ] Dashboard skeleton against seeded dummy rows from the contract (lane 4, Oct 12)

**Week 2 · Oct 13 to 19 · real data flows end to end**

- [ ] DAG scheduled daily on Astronomer, runs green two days in a row (lane 1)
- [ ] All marts built with dbt tests passing (lanes 2 + 3)
- [ ] Signal marts match hand-built fixtures; condition matrix asserted cell by cell (lane 3)
- [ ] Dashboard v1 on real marts (lane 4)
- [ ] Failure alerting on the DAG; observability notes for the demo (lanes 1 + 5)

**Week 3 · Oct 20 to 27 · integrate, freeze, rehearse**

- [ ] Oct 20 class time used as the integration session: fix the ugly joints (all)
- [ ] Feature freeze Friday Oct 23 (all)
- [ ] Demo script with fallback (recording or screenshots) in case GCP misbehaves live (lane 5)
- [ ] Dry run + stakeholder Q&A prep: "why these stocks", "what makes it fire" (all)
- [ ] Phase 1 presentation, Oct 27

## Housekeeping that starts now

- [ ] AI-use appendix: a running log of prompts, outputs and tools used, required by the syllabus; reconstructing it in December is painful (all, lane 5 owns the file)
- [ ] Decision log: one page of why-answers (why breadth over a basket average, why these tickers, why GCP); this is what the instructor's 40% evaluation and the stakeholder Q&A reward (lane 3 + lane 5)
