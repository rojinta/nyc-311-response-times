"""Build the analysis tables from the raw monthly files and save every result as a CSV.

Usage:  python3 build.py
Needs:  data/raw/311_YYYY-MM.csv.gz  (see get_311_data.py)
Makes:  nyc311.duckdb (database) and results/out_*.csv
"""
import pathlib
import duckdb

ROOT = pathlib.Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
files = sorted(RAW.glob("311_*.csv.gz"))
if not files:
    raise SystemExit("No files in data/raw. Run get_311_data.py first.")

con = duckdb.connect(str(ROOT / "nyc311.duckdb"))
con.execute(
    "create or replace table raw as select * from "
    "read_csv(?, all_varchar=true, union_by_name=true, filename=true)",
    [str(RAW / "311_*.csv.gz")],
)
print("raw rows:", con.execute("select count(*) from raw").fetchone()[0])

for f in sorted((ROOT / "sql").glob("0[1-6]_*.sql")):
    con.execute(f.read_text())
    print("ran", f.name)

(ROOT / "results").mkdir(exist_ok=True)
tables = [t for (t,) in con.execute(
    "select table_name from information_schema.tables where table_name like 'out_%' order by 1").fetchall()]
for t in tables:
    con.execute(f"copy {t} to '{ROOT / 'results' / (t + '.csv')}' (header)")
print("saved", len(tables), "result tables to results/")
