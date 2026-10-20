# Decision Log

## Dashboard tool and deployment

- Recorded: 2026-10-20
- Owner: Yuanhao (Myhill), Lane 4
- Decision: Streamlit for the dashboard, with Cloud Run as the deployment target.
- Alternative considered: Looker, which offers a simpler managed BigQuery connection.
- Reason: Streamlit gives us control over the verdict cards, event annotations, and member views in Python. The prototype already runs against real development marts.
- Tradeoff: the team maintains an application image, dependency versions, runtime identity, and access configuration. Cloud Run deployment and team access still need live verification.
- Review: pending teammate review in the Lane 4 PR.

### Data and display boundary

All signal calculations stay in dbt. The dashboard reads daily_signals, daily_drawdowns, and basket_members. Its member query uses the latest signal's trading date. Percentage formatting, sorting, date filtering, and freshness notices are display operations.

Development uses marts_dev; production explicitly selects marts. Failed production reads remain visible. The display warns after 72 hours since calculation or at least two weekday sessions of signal-date lag, allowing the evening update until 7pm ET. The weekday check excludes weekends but does not model exchange holidays; Lane 2 owns source freshness checks.

The generic basket-audit warning is implemented. The final AI-specific qualifier will be agreed with Lane 3 before acceptance of #51.
