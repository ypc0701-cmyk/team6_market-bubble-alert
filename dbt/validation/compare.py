"""Diff the dbt marts (DuckDB) against the oracle CSVs, every column, every row.
usage: python compare.py dev.duckdb expected_dir/ [marts_schema]  (default marts_duck, per generate_schema_name with target duck)"""
import sys
import duckdb
import pandas as pd
import numpy as np

db, exp = sys.argv[1], sys.argv[2]
schema = sys.argv[3] if len(sys.argv) > 3 else "marts_duck"
con = duckdb.connect(db, read_only=True)
keys = {"daily_drawdowns": ["trade_date", "ticker"], "credit_daily": ["trade_date"],
        "daily_signals": ["trade_date"], "episodes": ["episode_id"]}
bad = 0
for tbl, key in keys.items():
    got = con.execute(f"select * from {schema}.{tbl}").df().drop(columns=["computed_at"])
    want = pd.read_csv(f"{exp}/{tbl}.csv")
    for c in want.columns:
        if c.endswith("_date") or c == "trade_date":
            want[c] = pd.to_datetime(want[c]).dt.date
            got[c] = pd.to_datetime(got[c]).dt.date
    got = got.sort_values(key).reset_index(drop=True)
    want = want.sort_values(key).reset_index(drop=True)
    print(f"== {tbl}: dbt {got.shape} oracle {want.shape}")
    if list(got.columns) != list(want.columns):
        print("   column mismatch:", set(got.columns) ^ set(want.columns)); bad += 1
    m = got.merge(want, on=key, how="outer", suffixes=("_dbt", "_orc"), indicator=True)
    if (m["_merge"] != "both").any():
        print("   row mismatch:", m[m["_merge"] != "both"][key + ["_merge"]].head()); bad += 1
    for c in want.columns:
        if c in key:
            continue
        a, b = m[c + "_dbt"], m[c + "_orc"]
        if pd.api.types.is_numeric_dtype(b) and not pd.api.types.is_bool_dtype(b):
            a = pd.to_numeric(a, errors="coerce"); b = pd.to_numeric(b, errors="coerce")
            diff = ~(np.isclose(a.fillna(np.nan), b.fillna(np.nan), rtol=1e-9, atol=1e-9, equal_nan=True))
        else:
            a = a.astype("string").fillna("<null>").str.lower(); b = b.astype("string").fillna("<null>").str.lower()
            diff = (a != b).to_numpy(dtype=bool)
        n = int(diff.sum())
        if n:
            bad += 1
            ex = m.loc[diff, key + [c + "_dbt", c + "_orc"]].head(3)
            print(f"   {c}: {n} differences\n{ex.to_string(index=False)}")
print("ALL MATCH" if not bad else f"{bad} problem(s)")
