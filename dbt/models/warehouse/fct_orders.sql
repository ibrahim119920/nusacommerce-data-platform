-- Grain: one current order, with customer attributes resolved at order creation.
select o.*,c.customer_sk,(o.created_at at time zone 'Asia/Jakarta')::date as order_date
from {{ ref('stg_orders') }} o
left join {{ ref('dim_customer') }} c on o.customer_id=c.customer_id
 and o.created_at>=c.valid_from and (c.valid_to is null or o.created_at<c.valid_to)
