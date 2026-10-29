-- 06_never_closed.sql : Q5 Which requests are still open after 6+ months?
-- Cohort = requests created Oct 2025 - Mar 2026 (>= ~6 months before the 2026-10-26 snapshot).

create or replace table out_open_agency as
select agency, count(*) as requests,
       count(*) filter (where not is_closed) as still_open,
       round(100.0 * count(*) filter (where not is_closed) / count(*), 1) as pct_still_open
from clean where in_cohort_6m
group by agency having count(*) >= 3000
order by pct_still_open desc;

create or replace table out_open_complaint as
select complaint, count(*) as requests,
       count(*) filter (where not is_closed) as still_open,
       round(100.0 * count(*) filter (where not is_closed) / count(*), 1) as pct_still_open
from clean where in_cohort_6m
group by complaint having count(*) >= 3000
qualify row_number() over (order by count(*) filter (where not is_closed) desc) <= 15
order by still_open desc;

create or replace table out_open_status as
select status, count(*) as still_open
from clean where in_cohort_6m and not is_closed
group by status order by 2 desc;

-- How much of the "open backlog" is concentrated?
create or replace table out_open_concentration as
select complaint, count(*) as still_open,
       round(100.0 * count(*) / sum(count(*)) over (), 1) as pct_of_backlog,
       round(100.0 * sum(count(*)) over (order by count(*) desc) / sum(count(*)) over (), 1) as cumulative_pct
from clean where in_cohort_6m and not is_closed
group by complaint
qualify row_number() over (order by count(*) desc) <= 10
order by still_open desc;
