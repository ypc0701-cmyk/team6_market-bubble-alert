# Lane 3 validation fixtures

Three scripts that check the marts against an implementation that shares no code with them.

| File | What it does |
|---|---|
| `gen_scenario.py` | Writes a synthetic `prices_raw.csv`: 1,800 trading days (seven years from the 2024-10-01 backfill start) for all 24 symbols in the seed, shaped so the dial visits every level and every `armed_state_change` value: armed, rearmed, disarmed_quiet, armed again, disarmed_ceiling. NBIS and SPCX list inside the window (SPCX with an IPO pop), one IREN price row is missing, SMCI is removed from the speculative basket on day 1200 (via `basket_members_scenario.csv`), the newest day is a partial load, and there is a credit-only stress spell and an off-pattern decline. The timeline is in the docstring. Deterministic (seeded). |
| `oracle.py` | The Methodology implemented a second time, in plain Python with an explicit day-by-day state machine for episodes and the armed clock. Writes the four marts as CSVs. Where the SQL uses window functions and arming intervals, this loops, so a logic error in one is unlikely to be mirrored in the other. |
| `compare.py` | Diffs every column of every row of the dbt marts against the oracle CSVs (floats at 1e-9, nulls as values). |
| `load_duck.py` | Loads a `prices_raw.csv` into a DuckDB file as `raw.prices_raw` and creates the `staging_duck.stg_prices` view the marts read, for running the dbt project locally without BigQuery. |

`expected/` holds the oracle's `daily_signals.csv` and `episodes.csv` for the scenario, as the answer key. The scenario's `prices_raw.csv` and the per-ticker expectations are large and regenerate in seconds.

## Run locally (DuckDB, no GCP needed)

```
pip install dbt-duckdb duckdb pandas
python dbt/validation/gen_scenario.py /tmp/scn dbt/seeds/basket_members.csv   # also writes basket_members_scenario.csv (real roster + one removal)
python dbt/validation/oracle.py /tmp/scn/prices_raw.csv /tmp/scn/basket_members_scenario.csv /tmp/scn/expected
python dbt/validation/load_duck.py /tmp/dev.duckdb /tmp/scn/prices_raw.csv /tmp/scn/basket_members_scenario.csv   # also creates staging_duck.stg_prices and loads the scenario seed
# profiles.yml: profile ai_bubble_monitor, target duck: type duckdb, path /tmp/dev.duckdb, schema main
cd dbt && dbt build --vars '{gcp_project: dev}' --exclude stg_prices resource_type:seed   # the loader built stg_prices and the scenario seed
python validation/compare.py /tmp/dev.duckdb /tmp/scn/expected   # prints ALL MATCH (marts land in marts_duck per generate_schema_name)
```

The models are written in the dialect intersection of BigQuery and DuckDB (dbt's cross-database macros cover `dateadd`, `datediff`, `current_timestamp` and type names), which is what makes this possible. Against BigQuery the same project runs unchanged; `partition_by` and `cluster_by` apply there only.

## Status

Oct 20, 2026: all tests pass in DuckDB on the scenario (99, with the scenario seed) and on `docs/dummy_rows/prices_raw.csv`; `compare.py` reports ALL MATCH on all four marts. The SMCI removal case was added after Ahrar's review of #46 found that `roster_changed_today` could not see removals; against the old model, `compare.py` reports exactly one difference, on the removal day. On BigQuery (Oct 18, before these changes): 120/120.