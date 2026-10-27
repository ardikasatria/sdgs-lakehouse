-- Dibangkitkan dari config/mesh/dp_rilis.yaml; jangan disunting.
select r.*, s.keluarga, s.boleh_tayang
from {{ ref('dim_rilis') }} r
join {{ ref('dim_sumber') }} s on s.sumber = r.sumber
