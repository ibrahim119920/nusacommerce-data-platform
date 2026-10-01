select day::date as date_day,extract(year from day)::int as year,
 extract(month from day)::int as month,extract(day from day)::int as day
from generate_series(timestamp '2026-09-01',timestamp '2026-10-31',interval '1 day') day
