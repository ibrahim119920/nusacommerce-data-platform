-- Cash-flow grain: date x currency. A refund-only day can have negative net.
with movements as (
 select payment_date as date_day,currency,amount as revenue,0::numeric as refund
 from {{ ref('fct_payments') }} where status='succeeded'
 union all
 select refund_date,currency,0::numeric,amount from {{ ref('fct_refunds') }}
)
select date_day,currency,sum(revenue) as revenue,sum(refund) as refund,
 sum(revenue)-sum(refund) as net
from movements group by date_day,currency
