-- 04_geography.sql : Q3 Does geography matter once we control for WHAT people report?
-- Raw borough medians mix two effects: (a) complaint mix, (b) borough handling.
-- Fix: compare each borough's median to the CITYWIDE median for the SAME complaint type,
-- then average those ratios weighted by the borough's own complaint volume (an index; 1.00 = citywide norm).

-- Same-second closures (zero_dur) are NOT spread evenly: e.g. 47% of Manhattan DEP Water System requests vs 2% in
-- Staten Island. They look administrative, so the PRIMARY geography analysis excludes them; the version with them is
-- kept below as a robustness check.
create or replace table city_norm as
select complaint, count(*) as city_requests, median(hrs) as city_median
from clean
where in_cohort_90d and is_closed and not zero_dur and borough is not null
group by complaint
having count(*) >= 2000 and median(hrs) > 0;

create or replace table borough_complaint as
select c.borough, c.complaint, count(*) as requests, median(c.hrs) as med_hrs,
       median(c.hrs) / n.city_median as ratio_to_city,
       n.city_median
from clean c join city_norm n using (complaint)
where c.in_cohort_90d and c.is_closed and not c.zero_dur and c.borough is not null
group by c.borough, c.complaint, n.city_median
having count(*) >= 300;

-- Raw vs mix-adjusted, side by side
create or replace table out_borough_index as
with raw_med as (
    select borough, round(median(hrs), 1) as raw_median_hrs, count(*) as requests
    from clean where in_cohort_90d and is_closed and not zero_dur and borough is not null
    group by borough
), adj as (
    select borough,
           round(sum(ratio_to_city * requests) / sum(requests), 2) as adjusted_index,
           sum(requests) as covered_requests
    from borough_complaint group by borough
)
select r.borough, r.requests, r.raw_median_hrs, a.adjusted_index, a.covered_requests,
       rank() over (order by r.raw_median_hrs desc)  as raw_rank,
       rank() over (order by a.adjusted_index desc)  as adjusted_rank
from raw_med r join adj a using (borough)
order by adjusted_index desc;

-- Robustness check: same index INCLUDING same-second closures
create or replace table out_borough_index_withzero as
with cn as (
    select complaint, median(hrs) as city_median
    from clean where in_cohort_90d and is_closed and borough is not null
    group by complaint having count(*) >= 2000 and median(hrs) > 0
), bc as (
    select c.borough, c.complaint, count(*) as requests, median(c.hrs) / cn.city_median as ratio
    from clean c join cn using (complaint)
    where c.in_cohort_90d and c.is_closed and c.borough is not null
    group by c.borough, c.complaint, cn.city_median having count(*) >= 300
)
select borough, round(sum(ratio * requests) / sum(requests), 2) as adjusted_index_with_zero
from bc group by borough order by 2 desc;

-- Which complaint types drive the borough gaps? (largest volume-weighted deviation)
create or replace table out_borough_drivers as
select borough, complaint, requests, round(med_hrs, 1) as median_hrs,
       round(city_median, 1) as city_median_hrs, round(ratio_to_city, 2) as ratio_to_city,
       round((med_hrs - city_median) * requests / 24.0) as excess_wait_days
from borough_complaint
qualify row_number() over (partition by borough order by (med_hrs - city_median) * requests desc) <= 3
order by borough, excess_wait_days desc;

-- Same-complaint head-to-head for the biggest complaint types
create or replace table out_same_complaint as
select complaint, borough, requests, round(med_hrs, 1) as median_hrs,
       round(ratio_to_city, 2) as ratio_to_city
from borough_complaint
where complaint in ('DOT - Street Condition','HPD - HEAT/HOT WATER','HPD - UNSANITARY CONDITION',
                    'NYPD - Illegal Parking','DSNY - Dirty Condition','DEP - Water System')
order by complaint, med_hrs desc;
