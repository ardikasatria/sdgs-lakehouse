-- Dibangkitkan dari config/mesh/dp_referensi.yaml; jangan disunting.
select * from {{ ref('dim_konsep') }}
