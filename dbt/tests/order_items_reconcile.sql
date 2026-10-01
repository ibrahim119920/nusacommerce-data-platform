select o.order_id from {{ ref('fct_orders') }} o
left join {{ ref('fct_order_items') }} i using(order_id)
group by o.order_id,o.amount having sum(i.line_amount) is distinct from o.amount
