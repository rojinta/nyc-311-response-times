"""Export the small CSVs that feed the dashboard. Run build.py first."""
import duckdb, pathlib
ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / 'dashboard_data'
OUT.mkdir(exist_ok=True)
con = duckdb.connect(str(ROOT / 'nyc311.duckdb'), read_only=True)
def save(name, sql):
    con.execute(f"copy ({sql}) to '{OUT}/{name}.csv' (header)")
    n = con.execute(f"select count(*) from ({sql})").fetchone()[0]
    print(name, n, 'rows')

# agencies: all-time volume + 90-day-follow-up speed stats
save('agencies', """
with vol as (
  select agency, count(*) requests, round(100.0*count(*)/sum(count(*)) over (),1) pct_of_all
  from clean group by agency),
spd as (
  select agency, count(*) cohort_requests, round(median(hrs),1) median_hrs, round(quantile_cont(hrs,0.9),1) p90_hrs,
    round(100.0*count(*) filter (where not (hrs<=168) or hrs is null)/count(*),1) pct_not_done_7d,
    round(100.0*count(*) filter (where not is_closed)/count(*),1) pct_no_close_date,
    round(100.0*count(*) filter (where zero_dur)/count(*) filter (where is_closed),1) pct_zero_dur,
    round(median(hrs) filter (where not zero_dur),1) median_excl_zero
  from clean where in_cohort_90d group by agency)
select v.agency,
  case v.agency when 'NYPD' then 'Police' when 'HPD' then 'Housing' when 'DSNY' then 'Sanitation'
    when 'DOT' then 'Transportation' when 'DEP' then 'Environmental Protection' when 'DPR' then 'Parks and Recreation'
    when 'DOB' then 'Buildings' when 'DOHMH' then 'Health and Mental Hygiene' when 'DHS' then 'Homeless Services'
    when 'TLC' then 'Taxi and Limousine' when 'DCWP' then 'Consumer and Worker Protection'
    when 'EDC' then 'Economic Development' else v.agency end agency_name,
  v.requests, v.pct_of_all, s.cohort_requests, s.median_hrs, s.p90_hrs, s.pct_not_done_7d, s.pct_no_close_date, s.pct_zero_dur, s.median_excl_zero
from vol v join spd s using (agency) where v.requests >= 10000 and s.cohort_requests >= 5000
order by v.requests desc""")

# complaints: speed + waiting burden
save('complaints', """
with w as (select complaint, sum(hrs)/24.0 wait_days from clean where in_cohort_90d and is_closed group by complaint),
tot as (select sum(wait_days) t from w)
select s.complaint, s.requests, s.median_hrs, s.p90_hrs, s.pct_not_done_7d, s.pct_no_close_date,
       round(w.wait_days) total_wait_days, round(100.0*w.wait_days/tot.t,1) pct_of_all_waiting
from (select complaint, count(*) requests, round(median(hrs),1) median_hrs, round(quantile_cont(hrs,0.9),1) p90_hrs,
        round(100.0*count(*) filter (where not (hrs<=168) or hrs is null)/count(*),1) pct_not_done_7d,
        round(100.0*count(*) filter (where not is_closed)/count(*),1) pct_no_close_date
      from clean where in_cohort_90d group by complaint having count(*)>=10000) s
join w using (complaint), tot
order by s.requests desc""")

# boroughs
save('boroughs', """
with mix as (
  select borough,
    round(100.0*count(*) filter (where agency='NYPD')/count(*),1) nypd_share_pct,
    round(100.0*count(*) filter (where agency in ('HPD','DOB'))/count(*),1) hpd_dob_share_pct
  from clean where in_cohort_90d and is_closed and not zero_dur and borough is not null group by borough)
select case p.borough when 'BRONX' then 'Bronx' when 'BROOKLYN' then 'Brooklyn' when 'MANHATTAN' then 'Manhattan' when 'QUEENS' then 'Queens' when 'STATEN ISLAND' then 'Staten Island' end borough, p.population, p.requests, p.requests_per_resident, p.pct_of_requests, p.pct_of_population,
       i.raw_median_hrs, i.adjusted_index, z.adjusted_index_with_zero, i.raw_rank, i.adjusted_rank, m.nypd_share_pct, m.hpd_dob_share_pct
from out_borough_percapita p
join out_borough_index i using (borough)
join out_borough_index_withzero z using (borough)
join mix m using (borough)
order by i.adjusted_index desc""")

save('borough_complaint', """
select case borough when 'BRONX' then 'Bronx' when 'BROOKLYN' then 'Brooklyn' when 'MANHATTAN' then 'Manhattan' when 'QUEENS' then 'Queens' when 'STATEN ISLAND' then 'Staten Island' end borough, complaint, requests, round(med_hrs,1) median_hrs, round(city_median,1) city_median_hrs,
       round(ratio_to_city,2) ratio_to_city
from borough_complaint order by complaint, med_hrs desc""")

save('heat_daily', "select strftime(d,'%Y-%m-%d') d, vol, med_hrs, med_hrs_7d_avg, vol_7d_avg from out_heat_daily order by d")

save('heat_quartiles', """
select vol_quartile, case vol_quartile when 1 then 'Quietest quarter' when 2 then 'Second quarter' when 3 then 'Third quarter' else 'Busiest quarter' end label,
       days, avg_daily_requests, median_wait_hrs from out_heat_busy_vs_quiet order by 1""")

save('surge', "select complaint, days, spearman, median_daily_vol, peak_daily_vol from out_surge_corr order by spearman desc")

save('open_agency', "select agency, requests, still_open, pct_still_open from out_open_agency order by pct_still_open desc")

save('open_complaint', """
with b as (select complaint, count(*) requests, count(*) filter (where not is_closed) still_open
           from clean where in_cohort_6m group by complaint),
tot as (select sum(still_open) t from b)
select complaint, requests, still_open, round(100.0*still_open/requests,1) pct_still_open,
       round(100.0*still_open/tot.t,1) pct_of_backlog,
       round(100.0*sum(still_open) over (order by still_open desc)/tot.t,1) cumulative_pct
from b, tot qualify row_number() over (order by still_open desc) <= 10 order by still_open desc""")

# headline: one row of precomputed totals
save('headline', """
select
  (select count(*) from clean) total_requests,
  '2025-10-01 to 2026-09-30' as window_dates,
  'Oct 2025 to Sep 2026' as window_label,
  (select round(sum(pct_of_all),1) from (select pct_of_all from out_agency_volume order by requests desc limit 3)) top3_agency_pct,
  (select round(median(hrs),1) from clean where in_cohort_90d and agency='NYPD') nypd_median_hrs,
  (select round(median(hrs),1) from clean where in_cohort_90d and agency='HPD') hpd_median_hrs,
  (select round(100.0*count(*) filter (where agency='HPD')/count(*),1) from clean where in_cohort_90d and is_closed) hpd_request_share_pct,
  (select round(100.0*sum(hrs) filter (where agency='HPD')/sum(hrs),1) from clean where in_cohort_90d and is_closed) hpd_wait_share_pct,
  (select count(*) from clean where in_cohort_6m and not is_closed) backlog_6m,
  (select round(100.0*sum(still_open) filter (where true)/ (select count(*) from clean where in_cohort_6m and not is_closed),1)
     from (select complaint, count(*) still_open from clean where in_cohort_6m and not is_closed group by 1 order by 2 desc limit 10)) backlog_top10_pct,
  (select count(*) from clean where not is_closed) no_close_total,
  (select count(*) from clean where zero_dur) same_second_closures,
  (select count(*) from raw) - (select count(*) from clean) dropped_impossible,
  (select round(100.0*(max(median_wait_hrs) filter (where vol_quartile=4) / max(median_wait_hrs) filter (where vol_quartile=1) - 1)) from out_heat_busy_vs_quiet) heat_busy_vs_quiet_pct,
  (select round(max(med_hrs) filter (where borough='BRONX') / max(med_hrs) filter (where borough='QUEENS'),1) from borough_complaint where complaint='DOT - Street Condition') street_bronx_vs_queens_x,
  (select round(max(med_hrs) filter (where borough='BRONX') / max(med_hrs) filter (where borough='QUEENS'),1) from borough_complaint where complaint='DEP - Water System') water_bronx_vs_queens_x""")

# each agency's share of closed requests next to its share of all waiting time (the slope chart)
save('agency_shares', """
with b as (select case when agency in ('NYPD','HPD','DSNY','DOT','DEP','DPR','DOB') then agency else 'Other' end agency, hrs
           from clean where in_cohort_90d and is_closed)
select agency,
  case agency when 'NYPD' then 'Police' when 'HPD' then 'Housing' when 'DSNY' then 'Sanitation' when 'DOT' then 'Transportation'
    when 'DEP' then 'Water and environment' when 'DPR' then 'Parks' when 'DOB' then 'Buildings' else 'All other agencies' end agency_name,
  round(100.0*count(*)/sum(count(*)) over (),1) pct_requests,
  round(100.0*sum(hrs)/sum(sum(hrs)) over (),1) pct_waiting
from b group by agency order by pct_waiting desc""")
