select o.order_date,c.city,c.membership,o.currency,
 count(*) as order_count,sum(o.amount) as order_amount
from {{ ref('fct_orders') }} o join {{ ref('dim_customer') }} c using(customer_sk)
where o.status <> 'cancelled'
group by o.order_date,c.city,c.membership,o.currency
