select *,(refunded_at at time zone 'Asia/Jakarta')::date as refund_date
from {{ source('landing','raw_refunds') }}
