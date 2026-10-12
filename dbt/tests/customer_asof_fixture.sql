-- The historical order must retain Jakarta/silver despite the later customer change.
select o.order_id from {{ ref('fct_orders') }} o join {{ ref('dim_customer') }} c using(customer_sk)
where o.order_id='ord-1001' and (c.city<>'Jakarta' or c.membership<>'silver')
