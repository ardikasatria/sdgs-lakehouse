-- Determinisme nilai pilihan: dalam satu rilis, satu kunci konsep hanya mempunyai satu observasi.
select konsep_id, wilayah_kode, periode_konsep, rincian_konsep, rilis_id, count(*) as n
from {{ ref('fakta_observasi') }}
group by konsep_id, wilayah_kode, periode_konsep, rincian_konsep, rilis_id
having count(*) > 1
