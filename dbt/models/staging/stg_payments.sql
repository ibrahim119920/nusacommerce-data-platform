with ranked as (
 select *, row_number() over(partition by payment_id order by version desc, ingested_at desc) as rn
 from {{ source('landing','raw_payment_versions') }}
)
select payment_id,order_id,version,(payload->>'amount')::numeric(18,2) as amount,
 payload->>'currency' as currency,payload->>'status' as status,
 (payload->>'updated_at')::timestamptz as paid_at
from ranked where rn=1
