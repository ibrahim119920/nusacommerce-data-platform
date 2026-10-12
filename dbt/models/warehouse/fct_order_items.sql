-- Grain: order_id x line_number. Price is captured at the transaction.
select md5(i.order_id || '|' || i.line_number::text) as order_item_sk,
 i.*,i.quantity*i.unit_price as line_amount,o.customer_sk,o.order_date,o.currency
from {{ source('landing','raw_order_items') }} i
join {{ ref('fct_orders') }} o using(order_id)
join {{ ref('dim_product') }} p using(product_id)
