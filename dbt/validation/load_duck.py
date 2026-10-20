import duckdb, sys, os
db, csvp = sys.argv[1], sys.argv[2]
seed = sys.argv[3] if len(sys.argv) > 3 else None  # optional seed CSV to use instead of dbt/seeds (run dbt with --exclude resource_type:seed)
if os.path.exists(db): os.remove(db)
con = duckdb.connect(db)
con.execute("create schema raw")
con.execute(f"""create table raw.prices_raw as select cast(trade_date as date) trade_date, ticker,
  cast("open" as double) "open", cast("high" as double) "high", cast("low" as double) "low", cast("close" as double) "close", cast(adj_close as double) adj_close,
  cast(nullif(volume,'') as bigint) volume, source, cast(ingested_at as timestamp) ingested_at, cast(nullif(run_id,'') as varchar) run_id
  from read_csv('{csvp}', header=true, all_varchar=true)""")
# Lane 2's stg_prices casts with BigQuery type names, so build the equivalent view here for local runs.
con.execute("create schema if not exists staging_duck")
con.execute("""create or replace view staging_duck.stg_prices as select trade_date, upper(trim(ticker)) as ticker, "open", "high", "low", "close",
  adj_close, volume, source, ingested_at, run_id from raw.prices_raw""")
print(con.execute("select count(*), min(trade_date), max(trade_date) from raw.prices_raw").fetchall())
if seed:
    con.execute("create schema if not exists marts_duck")
    con.execute(f"""create or replace table marts_duck.basket_members as select ticker, company_name, basket, profile,
      cast(listing_date as date) listing_date, cast(added_date as date) added_date, cast(nullif(removed_date,'') as date) removed_date,
      added_reason, nullif(removed_reason,'') removed_reason, nullif(notes,'') notes
      from read_csv('{seed}', header=true, all_varchar=true)""")
    print(con.execute("select count(*), count(removed_date) from marts_duck.basket_members").fetchall())
