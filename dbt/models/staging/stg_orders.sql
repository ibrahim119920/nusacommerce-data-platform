with ranked as (
 select *, row_number() over(partition by order_id order by version desc, ingested_at desc) as rn
 from {{ source('landing','raw_order_versions') }}
)
select order_id,version,payload->>'customer_id' as customer_id,
 payload->>'status' as status,(payload->>'amount')::numeric(18,2) as amount,
 payload->>'currency' as currency,(payload->>'created_at')::timestamptz as created_at,
 source_updated_at
from ranked where rn=1
