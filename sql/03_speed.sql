-- 03_speed.sql : Q2 How long does each agency / complaint take?
-- Uses only requests with >= ~90 days of follow-up (in_cohort_90d) so recent requests are not unfairly "fast".
-- Reported with three measures so open requests are never silently dropped:
--   median_hrs / p90_hrs : among CLOSED requests
--   pct_not_done_7d      : share NOT closed within 7 days (open requests count as not done)

create or replace table out_agency_speed as
select agency,
       count(*)                                                       as requests,
       round(median(hrs), 1)                                          as median_hrs,
       round(quantile_cont(hrs, 0.9), 1)                              as p90_hrs,
       round(100.0 * count(*) filter (where not (hrs <= 168)  or hrs is null) / count(*), 1) as pct_not_done_7d,
       round(100.0 * count(*) filter (where not is_closed) / count(*), 1)                    as pct_no_close_date
from clean
where in_cohort_90d
group by agency
having count(*) >= 5000
order by median_hrs desc;

create or replace table out_complaint_speed as
select complaint,
       count(*)                                                       as requests,
       round(median(hrs), 1)                                          as median_hrs,
       round(quantile_cont(hrs, 0.9), 1)                              as p90_hrs,
       round(100.0 * count(*) filter (where not (hrs <= 168) or hrs is null) / count(*), 1) as pct_not_done_7d,
       round(100.0 * count(*) filter (where not is_closed) / count(*), 1)                   as pct_no_close_date
from clean
where in_cohort_90d
group by complaint
having count(*) >= 10000
order by requests desc;

-- "Waiting burden": where do New Yorkers collectively spend the most time waiting?
create or replace table out_wait_burden as
with w as (
    select complaint, count(*) as requests, sum(hrs) / 24.0 as wait_days
    from clean where in_cohort_90d and is_closed
    group by complaint
)
select rank() over (order by wait_days desc)                       as rnk,
       complaint, requests,
       round(wait_days)                                            as total_wait_days,
       round(100.0 * wait_days / sum(wait_days) over (), 1)        as pct_of_all_waiting,
       round(100.0 * sum(wait_days) over (order by wait_days desc) / sum(wait_days) over (), 1) as cumulative_pct
from w
qualify rnk <= 15
order by rnk;

-- Sensitivity: do zero-duration requests change agency medians?
create or replace table out_zero_sensitivity as
select agency,
       count(*)                                                            as requests,
       round(100.0 * count(*) filter (where zero_dur) / count(*), 1)       as pct_zero_dur,
       round(median(hrs), 1)                                               as median_all,
       round(median(hrs) filter (where not zero_dur), 1)                   as median_excl_zero
from clean
where in_cohort_90d and is_closed
group by agency having count(*) >= 5000
order by pct_zero_dur desc;
