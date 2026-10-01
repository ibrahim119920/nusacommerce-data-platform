with refunds as (
 select order_id,sum(amount) as amount from {{ ref('fct_refunds') }} group by order_id
), payments as (
 select order_id,sum(amount) as amount from {{ ref('fct_payments') }}
 where status='succeeded' group by order_id
)
select r.order_id from refunds r left join payments p using(order_id)
where r.amount>coalesce(p.amount,0)
