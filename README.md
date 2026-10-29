# NYC 311 response times: what you complain about matters more than where you live

An analysis of 3.96 million NYC 311 service requests from October 2025 to September 2026. It asks one question: **how long do New Yorkers wait for a request to be closed, and what explains the difference?**

Dashboard: https://rojinta.github.io/nyc-311-response-times/

## The short answer

- **The agency handling the request decides the wait.** Police requests close in a median of 1.3 hours. Housing requests (HPD) take 82.6 hours, and 37.5% are still not done after a week.
- **Housing is 24.0% of closed requests but 48.3% of all the time spent waiting.** Police are 44.4% of closed requests but 0.6% of the waiting.
- **Borough rankings flip once you compare like with like.** Raw medians make Queens look fastest (5.2 hours) and Manhattan slowest (16.6 hours). That is mostly because police requests are 52% of Queens' mix, and police close fast. After comparing each borough with the citywide median for the same complaint types, the gaps are small: an index from 0.87 (Staten Island, which is uncertain) or 0.93 (Manhattan) up to 1.06 (Bronx), where 1.00 is the citywide norm.
- **Some services do differ by borough.** Street condition requests take 2.2 times as long in the Bronx as in Queens, and water system requests 3.7 times as long.
- **Surges slow some services.** On the busiest quarter of days, the median heat and hot water wait is 47.4 hours, against 31.6 on the quietest quarter (about 50% longer).
- **A few complaint types hold most of the requests that never close.** 45,311 requests from the first six months of the window still have no close date, and ten complaint types account for 78.6% of them.

## Data

NYC Open Data, [311 Service Requests from 2010 to Present](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9) (dataset `erm2-nwe9`), requests created 1 October 2025 to 30 September 2026, pulled on 26 October 2026. The raw files are not in this repository (about four million rows). `get_311_data.py` downloads them. Population figures are US Census Bureau Vintage 2025 estimates for 1 July 2025.

## Method

1. **Cleaning** (`sql/01_clean.sql`). 3,963,900 rows downloaded, all with unique IDs. 1,093 impossible rows were dropped (1,092 closed before they were created, one with a closing date in the future). 139,795 requests with no close date were kept and counted as not done.
2. **Fair comparison windows.** Speed figures use only requests created before 1 August 2026, so each has at least about 90 days to close. Otherwise recent requests would look fast just because they are new. The never-closed analysis uses requests created before 1 April 2026 (at least six months of follow-up).
3. **Three speed measures.** Median and 90th percentile time to close (among closed requests), and the share not closed within 7 days. Open requests count as not done in the last one, so agencies are not flattered by requests that never closed.
4. **Mix-adjusted borough index** (`sql/04_geography.sql`). For each complaint type, divide a borough's median by the citywide median. Then average those ratios, weighted by how many requests of each type the borough has. 1.00 is the citywide norm. Only complaint types with at least 2,000 citywide requests and at least 300 in the borough are used.
5. **Demand and speed** (`sql/05_demand.sql`). For each complaint type, the Spearman rank correlation between a day's request volume and that day's median wait, over days with at least 20 requests.
6. **Verification.** `validate.py` recomputes every dashboard dataset with pandas straight from the raw files, with no SQL, and compares. Everything matches to within rounding.

## Limits

- **"Closed" is not "fixed".** The data shows when an agency closed a request, not whether the problem was solved.
- **Same-second closures.** 65,910 requests were created and closed in the same second. They look administrative and are concentrated in certain complaint types and boroughs (for example 47% of Manhattan's water system requests versus 2% in Staten Island), so the borough analysis leaves them out. The agency and complaint speed figures keep them, which makes buildings, health, transportation and environmental protection look somewhat faster than they otherwise would. For buildings, the typical wait is 172.5 hours with them and 302.6 without. The police versus housing comparison is not affected (0.0% and 0.1% of their closed requests).
- **Typical wait covers closed requests only.** For types where most requests never close, such as helicopter noise (about 97% with no close date), it describes only the few that did.
- **Staten Island's index is uncertain.** It moves from 1.02 to 0.87 depending on whether same-second closures are included. The gaps between boroughs are small overall, and Bronx, Brooklyn and Queens are nearly tied.
- **The surge result is a correlation.** A cold snap could drive both request volume and response times. Busier days go with longer waits for heat and hot water and for most police complaint types, but the opposite way for a few others (down to -0.24 for sanitation dirty conditions).
- **Waiting totals are a floor.** They add up closed requests only.
- **Requests per resident mixes need and willingness to report.** A low rate may mean fewer problems or less reporting.
- **Recent data keeps changing.** Requests close after the pull date, so a new pull gives slightly different numbers.

## Reproduce it

```bash
python3 -m pip install -r requirements.txt
python3 get_311_data.py            # downloads data/raw/311_YYYY-MM.csv.gz (takes a while)
python3 build.py                   # cleans, runs sql/*.sql, writes results/out_*.csv
python3 export_dashboard_data.py   # writes the dashboard CSVs to dashboard_data/
python3 validate.py                # independent pandas check
```

## What is in here

| Path | Contents |
|---|---|
| `index.html`, `vendor/` | The dashboard page (open `index.html` through a web server, or publish it with GitHub Pages) and the d3 library it uses |
| `sql/` | Six SQL files, one per question: cleaning, volume, speed, geography, demand, never closed |
| `build.py` | Loads the raw files into DuckDB and runs the SQL |
| `export_dashboard_data.py` | Builds the small CSVs behind the dashboard |
| `validate.py` | Independent re-computation in pandas |
| `get_311_data.py` | Downloads the data from the Socrata API |
| `results/` | Every result table as CSV |
| `dashboard_data/` | The datasets behind the dashboard |

Built with SQL (DuckDB), Python (pandas) and d3. The data is public NYC Open Data.
