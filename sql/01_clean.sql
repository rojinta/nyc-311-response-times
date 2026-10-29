-- 01_clean.sql : typed, cleaned analysis table + borough populations
-- Source: NYC Open Data "311 Service Requests from 2010 to Present" (erm2-nwe9), created 2025-10-01 .. 2026-09-30
-- Data pulled 2026-10-26 (snapshot date used for follow-up windows).

create or replace table req as
select
    cast(unique_key as bigint)                       as unique_key,
    try_cast(created_date as timestamp)              as created,
    try_cast(closed_date  as timestamp)              as closed,
    agency,
    complaint_type,
    agency || ' - ' || complaint_type                as complaint,
    nullif(borough, 'Unspecified')                   as borough,
    status,
    open_data_channel_type                           as channel
from raw;

create or replace table clean as
with timed as (
    select *,
           date_diff('second', created, closed) / 3600.0 as hrs   -- hours from creation to closure
    from req
)
select
    unique_key, created, closed, agency, complaint_type, complaint, borough, status, channel,
    hrs,
    (closed is not null)                                  as is_closed,
    (hrs = 0)                                             as zero_dur,           -- created and closed in the same second
    -- follow-up cohorts: only compare requests that have had time to close
    (created <  timestamp '2026-08-01')                   as in_cohort_90d,      -- >= ~88 days of follow-up
    (created <  timestamp '2026-04-01')                   as in_cohort_6m        -- >= ~6 months of follow-up
from timed
where (hrs is null or hrs >= 0)                           -- drop closed-before-created (impossible); keep still-open rows (hrs NULL)
  and (closed is null or closed <= timestamp '2026-10-26'); -- drop close dates in the future

-- NOTE: NULL comparisons evaluate to NULL (not true) in a WHERE clause, so open requests must be kept
-- explicitly with `is null`. (An earlier draft used `not (hrs < 0)` and silently dropped all open requests.)

create or replace table pop as
select * from (values
    ('BRONX',         1406332),
    ('BROOKLYN',      2653963),
    ('MANHATTAN',     1664862),
    ('QUEENS',        2358182),
    ('STATEN ISLAND',  501290)
) t(borough, population);   -- Census Bureau Vintage 2025 estimates, July 1 2025
