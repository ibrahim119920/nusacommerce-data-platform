select 1 where
(select coalesce(sum(net),0) from {{ ref('daily_finance') }}) is distinct from
((select coalesce(sum(amount),0) from {{ ref('fct_payments') }} where status='succeeded')
 - (select coalesce(sum(amount),0) from {{ ref('fct_refunds') }}))
