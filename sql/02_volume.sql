-- 02_volume.sql : Q1 What does New York ask 311 for?

create or replace table out_headline as
select (select count(*) from raw)                         as raw_rows,
       count(*)                                           as clean_rows,
       (select count(*) from raw) - count(*)              as dropped_rows,
       count(*) filter (where not is_closed)              as no_close_date,
       count(*) filter (where zero_dur)                   as zero_duration,
       count(*) filter (where borough is null)            as borough_unspecified
from clean;

create or replace table out_agency_volume as
select agency,
       count(*)                                                        as requests,
       round(100.0 * count(*) / sum(count(*)) over (), 1)              as pct_of_all,
       round(100.0 * sum(count(*)) over (order by count(*) desc, agency)
                   / sum(count(*)) over (), 1)                          as cumulative_pct
from clean
group by agency
order by requests desc;

create or replace table out_top_complaints as
select rank() over (order by count(*) desc)                as rnk,
       complaint, count(*) as requests,
       round(100.0 * count(*) / sum(count(*)) over (), 2)  as pct_of_all
from clean
group by complaint
qualify rnk <= 20
order by rnk;

create or replace table out_monthly as
select strftime(created, '%Y-%m') as month,
       count(*) as requests,
       count(*) filter (where agency = 'NYPD') as nypd,
       count(*) filter (where agency = 'HPD')  as hpd,
       count(*) filter (where agency = 'DSNY') as dsny,
       count(*) filter (where agency not in ('NYPD','HPD','DSNY')) as other
from clean group by 1 order by 1;

create or replace table out_borough_percapita as
select c.borough, p.population,
       count(*)                                               as requests,
       round(count(*) * 1.0 / p.population, 3)                as requests_per_resident,
       round(100.0 * count(*) / sum(count(*)) over (), 1)     as pct_of_requests,
       round(100.0 * p.population / sum(p.population) over (), 1) as pct_of_population
from clean c join pop p using (borough)
group by c.borough, p.population
order by requests_per_resident desc;

create or replace table out_channel as
select channel, count(*) as requests,
       round(100.0 * count(*) / sum(count(*)) over (), 1) as pct
from clean group by 1 order by 2 desc;
