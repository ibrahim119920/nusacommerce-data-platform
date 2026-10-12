select (CAST(payload->>'event_time' AS timestamptz) at time zone 'Asia/Jakarta')::date as date_day,
 payload->>'event_type' as event_type,count(*) as event_count,
 count(distinct payload->>'customer_id') as unique_customers
from {{ source('landing','clickstream_events') }} group by 1,2
