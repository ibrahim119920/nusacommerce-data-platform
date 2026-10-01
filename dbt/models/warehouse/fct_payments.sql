select p.*,(paid_at at time zone 'Asia/Jakarta')::date as payment_date
from {{ ref('stg_payments') }} p
