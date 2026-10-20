import duckdb, sys, os
db, csvp = sys.argv[1], sys.argv[2]
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
