-- 05_demand.sql : Q4 Does a surge in demand slow responses?
-- Unit = (complaint type, day created). For each complaint type: correlation between that day's volume
-- and the median wait of requests created that day. Spearman (rank) correlation is used because wait
-- times are heavily skewed.

create or replace table daily as
select complaint, cast(created as date) as d,
       count(*) as vol, median(hrs) as med_hrs
from clean
where in_cohort_90d and is_closed
group by complaint, cast(created as date)
having count(*) >= 20;

create or replace table out_surge_corr as
with ranked as (
    select complaint, d, vol, med_hrs,
           rank() over (partition by complaint order by vol)     as r_vol,
           rank() over (partition by complaint order by med_hrs) as r_med
    from daily
), tot as (
    select complaint, count(*) as days, round(corr(r_vol, r_med), 2) as spearman,
           round(median(vol)) as median_daily_vol, max(vol) as peak_daily_vol
    from ranked group by complaint
)
select * from tot
where complaint in (select complaint from clean group by complaint order by count(*) desc limit 12)
  and days >= 60
order by spearman desc;

-- Heat/hot water : the clearest seasonal surge
create or replace table out_heat_daily as
select d, vol, round(med_hrs, 1) as med_hrs,
       round(avg(med_hrs) over (order by d rows between 6 preceding and current row), 1) as med_hrs_7d_avg,
       round(avg(vol)     over (order by d rows between 6 preceding and current row))    as vol_7d_avg
from daily where complaint = 'HPD - HEAT/HOT WATER' order by d;

create or replace table out_heat_busy_vs_quiet as
with t as (
    select d, vol, med_hrs, ntile(4) over (order by vol) as vol_quartile
    from daily where complaint = 'HPD - HEAT/HOT WATER'
)
select vol_quartile, count(*) as days, round(avg(vol)) as avg_daily_requests,
       round(median(med_hrs), 1) as median_wait_hrs
from t group by 1 order by 1;
