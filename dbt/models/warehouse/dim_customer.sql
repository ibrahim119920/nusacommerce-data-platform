-- History is supplied by a deterministic fixture emulating the upstream history feed.
select md5(customer_id || '|' || (valid_from at time zone 'UTC')::text) as customer_sk,
 customer_id,city,membership,valid_from,valid_to
from {{ source('landing','raw_customer_history') }}
