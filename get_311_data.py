"""Download NYC 311 service requests, one gzipped CSV per month, into data/raw/.

Source: NYC Open Data, "311 Service Requests from 2010 to Present" (dataset erm2-nwe9), Socrata API.
Usage:  python3 get_311_data.py
Change START/END to change the window. The analysis in this repo used Oct 2025 to Sep 2026,
pulled on 2026-10-26. Data for recent months keeps changing as requests close, so a new pull
will give slightly different numbers.
"""
import csv
import gzip
import pathlib
import time

import requests

URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.csv"
START = (2025, 10)
END = (2026, 9)
PAGE = 50000
COLUMNS = ("unique_key,created_date,closed_date,agency,complaint_type,descriptor,location_type,"
           "incident_zip,borough,status,community_board,latitude,longitude,open_data_channel_type")
OUT = pathlib.Path(__file__).resolve().parent / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)


def months():
    y, m = START
    while (y, m) <= END:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


for y, m in months():
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    where = f"created_date >= '{y}-{m:02d}-01T00:00:00' AND created_date < '{ny}-{nm:02d}-01T00:00:00'"
    path = OUT / f"311_{y}-{m:02d}.csv.gz"
    rows, offset = 0, 0
    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        writer = None
        while True:
            params = {"$select": COLUMNS, "$where": where, "$order": "unique_key", "$limit": PAGE, "$offset": offset}
            for attempt in range(5):
                r = requests.get(URL, params=params, timeout=120)
                if r.status_code == 200:
                    break
                time.sleep(5 * (attempt + 1))
            r.raise_for_status()
            batch = list(csv.reader(r.text.splitlines()))
            if len(batch) <= 1:
                break
            if writer is None:
                writer = csv.writer(f)
                writer.writerow(batch[0])
            writer.writerows(batch[1:])
            rows += len(batch) - 1
            offset += PAGE
    print(f"{y}-{m:02d}: {rows:,} rows")
